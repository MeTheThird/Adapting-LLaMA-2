# Adapting-LLaMA-2

## Dependencies

- python version 3.9.18
- seqeval version 1.2.2
- transformers version 4.35.0
- pandas version 2.1.2
- cuda version 11.9

## Getting Started

After installing the required dependencies above, first ensure that you have access to the Llama-2-7b-chat-hf model via Hugging Face by following the instructions to request access to the model at this [link](https://huggingface.co/meta-llama/Llama-2-7b-chat-hf). Next, download the MultiCoNER II dataset by following the instructions at this [link](https://multiconer.github.io/dataset), and then take all of the files associated with Bangla, Farsi, Hindi, English, Portuguese, Italian, and Ukrainian and put them into one folder (we will refer to this folder as ```base_folder``` from here on out).

Next, if you would like to use our less detailed prompting strategy with 5 few shot examples that are randomly sampled from each language's dataset at the beginning and then remain constant across all of the test sentences, work with ```llama_ner_init_run.py```. If you would like to use our more detailed prompting strategy with 10 few shot examples that are randomly sampled at the beginning and then remain constant across all of the test sentences, work with ```llama_ner.py```. Finally, if you would like to use our more detailed prompting strategy with 10 few shot examples that are randomly sampled for each test sentence in each language, work with ```llama_ner_sample_every.py```.

In the file you choose to work with, change ```INSERT_BASE_FOLDER_PATH_HERE``` to the path to ```base_folder```, and change every instance of ```INSERT_TOKEN_HERE``` to a huggingface token associated with your huggingface account that will grant you access to the Llama-2-7b-chat-hf model. Then, ideally ensuring that you have access to a GPU with sufficient memory (we used an NVIDIA A100 GPU which has 40GB of memory), run the desired python file to generate the output files for each language. The file with ```score``` in the name will be the evaluation score for that language, the file with ```predicted_vs_reference``` in its name will contain the predicted vs. reference tags for each test sentence for that language, and the file with ```decoded_responses``` in its name will contain the full LLM decoded responses for each test sentence for that language. In order to generate our custom NER evaluation scores, simply run the ```new_ner_metric.py``` Python file with the ```predicted_vs_reference``` files for the languages for which you want to generate our custom NER evaluation scores as command line arguments to the Python script.

The ```LLAMA_NER.ipynb``` notebook can also be used to perform the evaluations on Google Colab. It procedurally loads the data and model, and evaluates the performances of the model. Some of our evaluations were conducted on Google Colab using this notebook. The prompt creation method can be adjusted to try different ways of prompting.

## Random Seed Used

We used the pandas random seed ```16``` for our random sampling to generate our results.
