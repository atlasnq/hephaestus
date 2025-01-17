# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/05_HephaestusModel.ipynb (unless otherwise specified).

__all__ = ['HephaestusModel']

# Cell
#hide
from typing import Union, List, Optional, Tuple
import os
import subprocess
import re
import torch
import pandas as pd
from copy import deepcopy

import sys
sys.path.append("..")

from .EditOperations import *
from .CondenseEditOperations import *
from .AbstractMethod import *
from .IOUtils import *
from .DatasetConstruction import *

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
        self.__TRAIN_OUTPUT_PATH = os.path.join(self.__MODEL_DIR, "train_output.txt")
        self.__RAW_OUTPUT_PATH =   os.path.join(self.__MODEL_DIR, "raw_output.txt")
        self.__POST_OUTPUT_PATH =  os.path.join(self.__MODEL_DIR, "postprocessed_output.txt")
        self.__SAVE_MODEL_PREFIX = "model"
        self.__SAVE_MODEL_PATH =   os.path.join(self.__MODEL_DIR, self.__SAVE_MODEL_PREFIX)
        self.__FINAL_MODEL_PATH =  os.path.join(self.__MODEL_DIR, self.__SAVE_MODEL_PREFIX + "_final.pt")

        # create the modelDir directory if it doesn't already exist
        if not os.path.isdir(self.__MODEL_DIR):
            os.makedirs(self.__MODEL_DIR)

    def train(self,

        trainSource: str,
        trainTarget: str,
        validSource: str,
        validTarget: str,

        numCheckpoints: int = 10,
        numGPUs: int = 1,

        embeddingSize: int = 512,

        rnnType: str = "LSTM",
        rnnSize: int = 256,
        numLayers: int = 2,

        numTrainingSteps: int = 50000,
        numValidations: int = 10,
        dropout: int = 0.2

    ) -> None:
        """
        Trains the model with the given parameters. Files containing AbstractMethods should have one per line with
        tokens separated by spaces. 'source' files must contain AbstractMethods. 'target' files may contain
        AbstractMethods or CompoundOperations in machine string format.

        As the training progesses, checkpoint model files are created which follow the format `model_step_#.pt`, where
        `#` corresponds to the training step number. Once training is complete, the finalized model is outputted to
        `model_final.pt`. In addition, training command output is written to `train_output.txt`.

        Default parameter values are such that they resemble the most successful NMT model in
        [this paper](https://arxiv.org/pdf/1812.08693.pdf) as closely as possible.

        Parameters:
        - Data and vocabulary:
            - `trainSource`: Required. File name containing training source data. Must be buggy AbstractMethods.
            - `trainTarget`: Required. File name containing training target data. Can be either non-buggy
              AbstractMethods or CompoundOperations in machine string format.
            - `validSource`: Required. File name containing validation source data. Must be buggy AbstractMethods.
            - `validTarget`: Required. File name containing validation target data. Must be the same type of data which
              is contained in the file denoted by `trainTarget`.
        - General options:
            - `numCheckpoints`: Number of times a checkpoint model is saved; e.g. if `numTrainingSteps` is 50,000 and
              `numCheckpoints` is 10, then a checkpoint will be saved after every 5,000 training steps. Defaults to 10.
            - `numGPUs`: Number of GPUs to use concurrently during training. If set to 0, then the CPU is used. Defaults
              to 1.
        - Model options:
            - `embeddingSize`: Word embedding size for source and target. Defaults to 512.
        - Encoder/decoder options:
            - `rnnType`: Gate type to use in RNN encoder and decoder. Can be `"LSTM"` or `"GRU"`. Defaults to `"LSTM"`.
            - `rnnSize`: Size of encoder and decoder RNN hidden states. Defaults to 256.
            - `numLayers`: Number of layers each in the encoder and decoder. Defaults to 2.
        - Learning options:
            - `numTrainingSteps`: Number of training steps to perform. Defaults to 50,000.
            - `numValidations`: `validSteps`: Number of validations to perform during training; e.g. if `numTrainingSteps`
              is 50,000 and `numValidations` is 10, then validation will occur after every 5,000 training steps. Defaults
              to 10.
            - `dropout`: Dropout probability. Defaults to 0.2.
        """

        # write config file using same parameters as passed to this method, note that locals() contains self
        HephaestusModel.__writeConfigFile(**locals())

        # build vocabulary, first create empty files for the vocab
        for filename in (self.__SOURCE_VOCAB_PATH, self.__TARGET_VOCAB_PATH):
            open(filename, "w").close()
        runCommand('onmt_build_vocab -config "{}" -n_sample -1'.format(self.__CONFIG_PATH))

        # delete previous model files
        for file in os.listdir(self.__MODEL_DIR):
            if re.search(r"^" + self.__SAVE_MODEL_PREFIX + r"_(?:step_[0-9]+|final).pt$", file):
                os.remove(os.path.join(self.__MODEL_DIR, file))

        # train the model and write output to the appropriate file
        trainOutput = runCommand('onmt_train -config "{}"'.format(self.__CONFIG_PATH))
        with open(self.__TRAIN_OUTPUT_PATH, "w") as f:
            f.write(trainOutput)

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

    def getTrainingStats(self) -> pd.DataFrame:
        """
        Returns a pandas dataframe describing training statistics; the dataframe has the following columns:

        - `step`: The training step in increments of 50
        - `trainAccuracy`: Model accuracy with respect to the **training** set
        - `validAccuracy`: Validation accuracy. These values will likely not be present for every row.
        - `crossEntropy`: Cross-entropy value
        """

        # create empty dataframe and initialize trainStep value
        frame = pd.DataFrame(columns = ["step", "trainAccuracy", "validAccuracy", "crossEntropy"])
        trainStep = -1

        # read through lines of the training output file
        with open(self.__TRAIN_OUTPUT_PATH, "r") as f:

            for line in f:

                line = line.strip()

                # attempt to match against a line that has training accuracy and the like
                match = re.search(r"^\[[^\]]*INFO\] *Step *(\d+)/ *\d+; *acc: *(.+?);.+?xent: *(.+?);", line)
                if match:

                    trainStep = int(match.group(1))
                    accuracy = float(match.group(2))
                    xEntropy = float(match.group(3))

                    frame.loc[len(frame)] = [trainStep, accuracy, None, xEntropy]

                # attmpt to match against a line that has validation accuracy info
                match = re.search(r"^\[[^\]]*INFO\] *Validation accuracy: *((?:\d+\.)?\d+)", line)
                if match and trainStep > 0:
                    frame.at[len(frame) - 1, "validAccuracy"] = float(match.group(1))

        # set the type of the "step" column to int, then return the frame
        frame["step"] = frame["step"].astype(int)
        return frame

    def translate(self,
        buggy: Union[str, AbstractMethod, List[AbstractMethod]],
        modelFile: str = None,
        applyEditOperations: bool = True
    ) -> Union[Optional[AbstractMethod], List[Optional[AbstractMethod]]]:
        """
        Translates the given `buggy` AbstractMethods into supposedly fixed AbstractMethods, writes them to
        `<model_directory>/postprocessed_output.txt`, and then returns them. The raw output of the model is written
        to `<model_directory>/raw_output.txt` in case you want to access that as well. Depending on what type of
        value is passed to `buggy`, the return value of this method changes according to the following:

        | `buggy` type           | Return type                      |
        | :--------------------- | :------------------------------- |
        | `str` (a file)         | `List[Optional[AbstractMethod]]` |
        | `AbstractMethod`       | `Optional[AbstractMethod]`       |
        | `List[AbstractMethod]` | `List[Optional[AbstractMethod]]` |

        A `None` return value means that the model was unable to translate that abstract method correctly. This
        could be due to the model outputting non well-formed CompoundOperations, among other things. These will
        appear as blank lines in `postprocessed_output.txt`.

        Optional args:
        - `modelFile`: A `.pt` file which is used for translation instead of the default `model_final.pt`
        - `applyEditOperations`: When set to True, the model output is interpreted as CompoundOperations and a
          postprocessing stage occurs where the outputted CompoundOperations are applied to the inputted
          AbstractMethods. When set to False, the raw output is interpreted as AbstractMethods and returned
          without a postprocessing stage; in this case, the contents of `raw_output.txt` and
          `postprocessed_output.txt` are identical. If the model was trained with EditOperations,
          `applyEditOperations` should be True; if the model was trained with just AbstractMethods as in for
          the control group, then this should be False. Defaults to True.
        """

        # determine which model file to use, and raise an error if it doesn't exist
        if modelFile is None:
            modelFile = self.__FINAL_MODEL_PATH
        if not os.path.isfile(modelFile):
            raise FileNotFoundError("HephaestusModel: model not found -- {}".format(modelFile))

        # write the AbstractMethods to a file if they were given directly
        buggyFile = None
        if type(buggy) in (AbstractMethod, list):
            buggyFile = os.path.join(self.__MODEL_DIR, "input.txt")
            writeAbstractMethodsToFile(buggyFile, buggy if type(buggy) is list else [buggy])
        else:
            buggyFile = buggy

        # translate the buggy methods
        command = 'onmt_translate -model "{}" -src "{}" -output "{}"'.format(modelFile, buggyFile, self.__RAW_OUTPUT_PATH)
        if getYamlParameter(self.__CONFIG_PATH, "world_size") is not None: # if GPU should be used
            command += " --gpu 0"
        runCommand(command)

        # strip the last line of the output file because OpenNMT likes to put a newline at the end
        with open(self.__RAW_OUTPUT_PATH, "r+") as outputFile:
            lines = outputFile.readlines()
            lines[-1] = lines[-1].strip()
            outputFile.seek(0)
            outputFile.writelines(lines)
            outputFile.truncate()

        # get all inputted AbstractMethods
        inputMethods = []
        if type(buggy) in (AbstractMethod, list):
            inputMethods = buggy if type(buggy) is list else [buggy]
        else:
            inputMethods = readAbstractMethodsFromFile(buggyFile)

        # If edit ops should be applied, then extract the operations from the output file and attempt to
        # apply them to the input methods. Assign a None value to a fixed method if its corresponding
        # operations were not able to be read, or if the operations are illegal (i.e. modifies out of bounds
        # tokens). Copy input methods before applying edit operations so that the original remains unmodified.
        fixedMethods = []
        if applyEditOperations:
            operations = readCompoundOperationsFromFile(self.__RAW_OUTPUT_PATH)
            for inputMethod, opList in zip(inputMethods, operations):
                if opList is None:
                    fixedMethods.append(None)
                else:
                    try:
                        inputMethodCopy = deepcopy(inputMethod)
                        inputMethodCopy.applyEditOperations(opList)
                        fixedMethods.append(inputMethodCopy)
                    except IndexError as e:
                        fixedMethods.append(None)

        # Simply interpret the output as abstract methods if not interpreting as edit operations
        else:
            fixedMethods = readAbstractMethodsFromFile(self.__RAW_OUTPUT_PATH)

        # Make sure the number of fixed methods equals the number of inputted methods -- this can differ if the
        # model fails to translate one of the inputs.
        numFails = len(inputMethods) - len(fixedMethods)
        if numFails > 0:
            raise RuntimeError("HephaestusModel: failed to translate {} input(s)".format(numFails))

        # write the fixed methods to the postprocessed output file, substituting null methods with blank lines
        writeAbstractMethodsToFile(
            self.__POST_OUTPUT_PATH,
            [" " if method is None else method for method in fixedMethods]
        )

        # return fixed methods
        return fixedMethods if type(buggy) is list else fixedMethods[0]

    def __writeConfigFile(self, **kwargs) -> None:
        """
        Creates the config file. Takes the same arguments as `HephaestusModel.train`.
        """

        def makeHeader(label: str) -> str:
            """Makes a nice header for the config file sections."""
            return "#" * 80 + "\n# {0:<77}#\n".format(label) + "#" * 80

        # calculate some parameters which are defined differently in OpenNMT
        saveCheckpointSteps = max(kwargs["numTrainingSteps"] // kwargs["numCheckpoints"], 1)
        validSteps = max(kwargs["numTrainingSteps"] // kwargs["numValidations"], 1)

        lines = [
            '# AUTOGENERATED',
            '',
            makeHeader("GENERAL OPTIONS"),
            '',
            '# Base path for objects that will be saved, e.g. vocab, embeddings, etc.',
            'save_data: "{}"'.format(self.__SAVE_DATA_PATH.replace(os.path.sep, "/")),
            '',
            '# Base path for saved model checkpoints',
            'save_model: "{}"'.format(self.__SAVE_MODEL_PATH.replace(os.path.sep, "/")),
            '',
            '# Save a model checkpoint after X number of training steps',
            'save_checkpoint_steps: {}'.format(saveCheckpointSteps),
            '',
            '# Allow overwriting existing files in the model directory',
            'overwrite: true',
            '',
            makeHeader("VOCABULARY AND DATA"),
            '',
            '# Vocabularies will be written to these files',
            'src_vocab: "{}"'.format(self.__SOURCE_VOCAB_PATH.replace(os.path.sep, "/")),
            'tgt_vocab: "{}"'.format(self.__TARGET_VOCAB_PATH.replace(os.path.sep, "/")),
            '',
            '# Defines training and validation datasets. Data is already in the correct',
            '# format, so no need for transforms.',
            'data:',
            '    corpus_1:',
            '        path_src: "{}"'.format(kwargs["trainSource"].replace(os.path.sep, "/")),
            '        path_tgt: "{}"'.format(kwargs["trainTarget"].replace(os.path.sep, "/")),
            '        transforms: []',
            '        weight: 1',
            '    valid:',
            '        path_src: "{}"'.format(kwargs["validSource"].replace(os.path.sep, "/")),
            '        path_tgt: "{}"'.format(kwargs["validTarget"].replace(os.path.sep, "/")),
            '        transforms: []',
            '',
            makeHeader("MODEL"),
            '',
            '# Overall type of model, here we use seq2seq',
            'model_task: seq2seq',
            '',
            '# Attention method to use in encoder and decoder, mlp means Bahdanau',
            'global_attention: mlp',
            '',
            '# Do not use an additional layer between the encoder and decoder',
            'bridge: false',
            '',
            '# Word embedding size for source and target',
            'word_vec_size: {}'.format(kwargs["embeddingSize"]),
            '',
            makeHeader("ENCODER / DECODER"),
            '',
            '# Gate type to use in RNN encoder and decoder',
            'rnn_type: {}'.format(kwargs["rnnType"]),
            '',
            '# Encoder and decoder are always RNNs',
            'encoder_type: rnn',
            'decoder_type: rnn',
            '',
            '# Size of encoder and decoder RNN hidden states',
            'rnn_size: {}'.format(kwargs["rnnSize"]),
            '',
            '# Number of layers in each the encoder and decoder',
            'layers: {}'.format(kwargs["numLayers"]),
            '',
            makeHeader("LEARNING AND OPTIMIZATION"),
            '',
            '# Number of training steps to perform',
            'train_steps: {}'.format(kwargs["numTrainingSteps"]),
            '',
            '# Perform validation every X number of training steps',
            'valid_steps: {}'.format(validSteps),
            '',
            '# Dropout probability',
            'dropout: {}'.format(kwargs["dropout"]),
            '',
            '# Use the Adam optimization method',
            'optim: adam',
            '',
            '# Starting learning rate -- Tufano et al. use 0.0001',
            'learning_rate: 0.0001',
            ''
        ]

        numGPUs = kwargs["numGPUs"]
        gpuLines = []
        if numGPUs > 0:
            gpuLines += [
                '# Train using {} GPU{}'.format(numGPUs, "s" if numGPUs > 1 else ""),
                'world_size: {}'.format(numGPUs),
                'gpu_ranks:',
                *["- {}".format(i) for i in range(numGPUs)],
                ''
            ]
        else:
            gpuLines += ["# Train using the CPU, so no world_size parameter is provided", ""]

        lines = lines[:16] + gpuLines + lines[16:]

        with open(self.__CONFIG_PATH, "w") as file:
            file.write("\n".join(lines))