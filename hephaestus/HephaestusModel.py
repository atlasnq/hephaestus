# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/04_HephaestusModel.ipynb (unless otherwise specified).

__all__ = ['HephaestusModel']

# Cell
#hide
from typing import Union, List, Optional, Tuple
import os
import subprocess
import re

import sys
sys.path.append("..")

from .EditOperations import *
from .CondenseEditOperations import *
from .AbstractMethod import *
from .IOUtils import *

# Cell
class HephaestusModel:
    """
    The `HephaestusModel` is the means through which buggy AbstractMethods are translated into fixed ones. Each
    `HephaestusModel` occupies a directory which contains stored models, vocabularies, and configuration files.

    Required args:
    - `modelDir`: The directory which stores files pertaining to the model. You can use a directory which already
      contains the necessary files (previously generated from a different `HephaestusModel`), in which case the
      model will not have to be trained again. If you provide a directory that does not exist, the `HephaestsuModel`
      will attempt to create it.
    """

    def __init__(self, modelDir: str) -> None:

        # set up constants
        self.__MODEL_DIR =         modelDir if os.path.sep == "/" else modelDir.replace("/", os.path.sep)
        self.__CONFIG_PATH =       os.path.join(self.__MODEL_DIR, "config.yaml")
        self.__SAVE_DATA_PATH =    os.path.join(self.__MODEL_DIR, "save_data")
        self.__SOURCE_VOCAB_PATH = os.path.join(self.__MODEL_DIR, "save_data.vocab.src")
        self.__TARGET_VOCAB_PATH = os.path.join(self.__MODEL_DIR, "save_data.vocab.tgt")
        self.__OUTPUT_PATH =       os.path.join(self.__MODEL_DIR, "output.txt")
        self.__SAVE_MODEL_PREFIX = "model"
        self.__SAVE_MODEL_PATH =   os.path.join(self.__MODEL_DIR, self.__SAVE_MODEL_PREFIX)
        self.__FINAL_MODEL_PATH =  os.path.join(self.__MODEL_DIR, self.__SAVE_MODEL_PREFIX + "_final.pt")

        # create the modelDir directory if it doesn't already exist
        if not os.path.isdir(self.__MODEL_DIR):
            os.mkdir(self.__MODEL_DIR)

    def train(self,

        trainSource: str,
        trainTarget: str,
        validSource: str,
        validTarget: str,

        vocabSamples: int =       10000,
        numGPUs: int =                1,
        trainSteps: int =          1000,
        validSteps: int =          None,
        saveCheckpointSteps: int = None

    ) -> None:
        """
        Trains the model with the given parameters. Files containing AbstractMethods should have one per line with
        tokens separated by spaces. 'source' files must contain AbstractMethods. 'target' files may contain
        AbstractMethods or EditOperations.

        As the training progesses, checkpoint model files are created which follow the format `model_step_#.pt`, where
        `#` corresponds to the training step number. Once training is complete, the finalized model is outputted to
        `model_final.pt`.

        Required args:
        - `trainSource`: File name contatining training source data, must be buggy AbstractMethods.
        - `trainTarget`: File name contatining training target data, can be fixed AbstractMethods or EditOperations
          describing buggy -> fixed.
        - `validSource`: File name contatining validation source data, must be buggy AbstractMethods.
        - `validTarget`: File name contatining validation target data, must be the same type of data provided in
          `trainTarget`.

        Optional args:
        - `vocabSamples`: Number of transformed samples per corpus to use when building vocabulary. Defaults to 10000.
        - `numGPUs`: Number of GPUs to use concurrently during training. If set to 0, then the CPU is used. Defaults to
          1.
        - `trainSteps`: Number of training steps to go through. Defaults to 1000.
        - `validSteps`: Number of training steps after which each validation occurs; e.g. if `trainSteps` is 1000 and
          `validSteps` is 500, then validation will occur after training steps 500 and 1000. Defaults to
          `trainSteps` / 2.
        - `saveCheckpointSteps`: Number of training steps after which model checkpoints are saved; e.g. if `trainSteps`
          is 1000 and 'saveCheckpointSteps' is 500, then the model will be saved in after training steps 5000 and 1000.
          Defaults to `trainSteps` / 2.
        """

        # TODO: Right now this is just the default model, we should tune the parameters so that it's
        # somewhat specialized to our use case and it works better.

        # determine number of validation and checkpoint steps if none were given
        if validSteps is None:
            validSteps = max(trainSteps // 2, 1)
        if saveCheckpointSteps is None:
            saveCheckpointSteps = max(trainSteps // 2, 1)

        # write config file
        self.__writeConfigFile(trainSource, trainTarget, validSource, validTarget, numGPUs = numGPUs,
                trainSteps = trainSteps, validSteps = validSteps, saveCheckpointSteps = saveCheckpointSteps)

        # build vocabulary
        runCommand('onmt_build_vocab -config "{}" -n_sample {}'.format(self.__CONFIG_PATH, vocabSamples))

        # delete previous model files
        for file in os.listdir(self.__MODEL_DIR):
            if re.search(r"^" + self.__SAVE_MODEL_PREFIX + r"_(?:step_[0-9]+|final).pt$", file):
                os.remove(os.path.join(self.__MODEL_DIR, file))

        # train the model
        runCommand('onmt_train -config "{}"'.format(self.__CONFIG_PATH))

        # find and release the highest trained model
        latestModel = None
        maxNum = 0
        for file in os.listdir(self.__MODEL_DIR):
            match = re.search(r"^" + self.__SAVE_MODEL_PREFIX + r"_(?:step_([0-9]+)|final).pt$", file)
            if match:
                stepNum = int(match.group(1))
                if stepNum > maxNum:
                    latestModel = os.path.join(self.__MODEL_DIR, file)
                    maxNum = stepNum

        if latestModel is not None:
            runCommand('onmt_release_model --model "{}" --output "{}"'.format(latestModel, self.__FINAL_MODEL_PATH))

    def translate(self,
        buggy: Union[str, AbstractMethod, List[AbstractMethod]],
        modelFile: str = None,
        applyEditOperations: bool = True
    ) -> Union[AbstractMethod, List[AbstractMethod]]:
        """
        Translates the given `buggy` AbstractMethods into supposedly fixed AbstractMethods, writes them to
        `<model_directory>/output.txt`, and then returns them. Depending on what type of value is passed to
        `buggy`, the return value of this method changes according to the following:

        | `buggy` type           | Return type            |
        | :--------------------- | :--------------------- |
        | `str` (a file)         | `List[AbstractMethod]` |
        | `AbstractMethod`       | `AbstractMethod`       |
        | `List[AbstractMethod]` | `List[AbstractMethod]` |

        Optional args:
        - `modelFile`: A `.pt` file which is used for translation instead of the default `model_final.pt`
        - `applyEditOperations`: When set to True, the model output is interpreted as EditOperations -- a
          postprocessing stage occurs where the outputted EditOperations are applied to the inputted
          AbstractMethods. When set to False, the raw output is interpreted as AbstractMethods and returned
          without a postprocessing stage. If the model was trained with EditOperations, `applyEditOperations`
          should be True; if the model was trained with just AbstractMethods as in for the control group,
          then this should be False. Defaults to True.
        """

        # determine which model file to use, and raise an error if it doesn't exist
        if modelFile is None:
            modelFile = self.__FINAL_MODEL_PATH
        if not os.path.isfile(modelFile):
            raise FileNotFoundError("Hephaestus: model not found -- {}".format(modelFile))

        # write the AbstractMethods to a file if they were given directly
        buggyFile = None
        if type(buggy) in (AbstractMethod, list):
            buggyFile = os.path.join(self.__MODEL_DIR, "input.txt")
            writeAbstractMethodsToFile(buggyFile, buggy if type(buggy) is list else [buggy])
        else:
            buggyFile = buggy

        # translate the buggy methods
        command = 'onmt_translate -model "{}" -src "{}" -output "{}"'.format(modelFile, buggyFile, self.__OUTPUT_PATH)
        if getYamlParameter(self.__CONFIG_PATH, "world_size") is not None: # if GPU should be used
            command += "-gpu 0"
        runCommand(command)

        # get all inputted AbstractMethods
        inputMethods = []
        if type(buggy) in (AbstractMethod, list):
            inputMethods = buggy if type(buggy) is list else [buggy]
        else:
            with open(buggyFile, "r") as inputFile:
                inputMethods = [AbstractMethod(line.strip()) for line in inputFile.readlines()]

        # get all lines of output
        outputLines = []
        with open(self.__OUTPUT_PATH, "r") as outputFile:
            outputLines = [line.strip() for line in outputFile.readlines()]

        # iterate through input and output to determine the fixed AbstractMethods
        fixedMethods = []
        for inputMethod, outputLine in zip(inputMethods, outputLines):

            if applyEditOperations:
                # TODO: extract edit operations and apply them to the inputMethod
                # inputMethod.applyEditOperations(...)
                # fixedMethods.append(inputMethod)
                raise RuntimeError("HephaestusModel: postprocessing is not supported yet")

            else:
                # no postprocessing, just convert the raw output line directly to an AbstractMethod
                fixedMethods.append(AbstractMethod(outputLine))

        # return the fixed methods
        return fixedMethods if type(buggy) is list else fixedMethods[0]

    def __writeConfigFile(self, *args, **kwargs) -> None:
        """
        Creates the config file.
        """

        lines = [
            "# AUTOGENERATED",
            "",
            "# Samples will be writted to here",
            "save_data: {}".format(self.__SAVE_DATA_PATH.replace(os.path.sep, "/")),
            "",
            "# Vocabs will be written to these files",
            "src_vocab: {}".format(self.__SOURCE_VOCAB_PATH.replace(os.path.sep, "/")),
            "tgt_vocab: {}".format(self.__TARGET_VOCAB_PATH.replace(os.path.sep, "/")),
            "",
            "# Allow overwriting existing files in the directory",
            "overwrite: True",
            "",
            "# Data corpus",
            "data:",
            "    corpus_1:",
            "        path_src: {}".format(args[0].replace(os.path.sep, "/")),
            "        path_tgt: {}".format(args[1].replace(os.path.sep, "/")),
            "        transforms: []",
            "        weight: 1",
            "    valid:",
            "        path_src: {}".format(args[2].replace(os.path.sep, "/")),
            "        path_tgt: {}".format(args[3].replace(os.path.sep, "/")),
            "        transforms: []",
            "",
            "# Checkpoints will be saved here",
            "save_model: {}".format(self.__SAVE_MODEL_PATH.replace(os.path.sep, "/")),
            "save_checkpoint_steps: {}".format(kwargs["saveCheckpointSteps"]),
            "train_steps: {}".format(kwargs["trainSteps"]),
            "valid_steps: {}".format(kwargs["validSteps"]),
            ""
        ]

        numGPUs = kwargs["numGPUs"]
        if numGPUs > 0:
            lines += [
                "# Train using {} GPU{}".format(numGPUs, "s" if numGPUs > 1 else ""),
                "world_size: {}".format(numGPUs),
                "gpu_ranks:",
                *["- {}".format(i) for i in range(numGPUs)]
            ]
        else:
            lines += ["# Train using the CPU, so no world_size provided"]

        with open(self.__CONFIG_PATH, "w") as file:
            file.write("\n".join(lines))