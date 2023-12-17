# -*- coding: utf-8 -*-
"""LLAMA NER.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/15yRtGbAXJnqdebU0iGxtbMW3Bi5qqAJr
"""

# Importing
from transformers import AutoModelForTokenClassification, AutoTokenizer, AutoModelForCausalLM, AutoTokenizer
import pandas as pd
import seqeval.metrics
import json

def load_ner_data(file_path):
    # Create an empty DataFrame to hold tokens and tags
    data = pd.DataFrame(columns=["sentence_id", "words", "tags"])

    current_words = []
    current_tags = []
    sentence_id = 0
    sentences_data = []  # List to store each sentence's data

    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            # Check if the line is the start of a new sentence
            if not line or line.startswith('# id'):
                if current_words:  # Save the previous sentence
                    sentences_data.append({"sentence_id": sentence_id, "words": current_words, "tags": current_tags})
                    sentence_id += 1
                current_words = []
                current_tags = []
            else:
                # Split the line into columns
                parts = line.split()
                current_words.append(parts[0])
                current_tags.append(parts[-1])  # The last column is the tag

    # Using pandas.concat to add the list of sentence data to the DataFrame
    data = pd.concat([data, pd.DataFrame(sentences_data)], ignore_index=True)

    return data

def create_ner_prompt(language, examples, annotations):
    # BIO Tags included
    entity_types = (
        "Location (LOC): B-Facility, I-Facility, B-OtherLOC, I-OtherLOC, B-HumanSettlement, I-HumanSettlement, B-Station, I-Station\n"
        "Creative Work (CW): B-VisualWork, I-VisualWork, B-MusicalWork, I-MusicalWork, B-WrittenWork, I-WrittenWork, B-ArtWork, I-ArtWork, B-Software, I-Software\n"
        "Group (GRP): B-MusicalGRP, I-MusicalGRP, B-PublicCORP, I-PublicCORP, B-PrivateCORP, I-PrivateCORP, B-AerospaceManufacturer, I-AerospaceManufacturer, B-SportsGRP, I-SportsGRP, B-CarManufacturer, I-CarManufacturer, B-ORG, I-ORG\n"
        "Person (PER): B-Scientist, I-Scientist, B-Artist, I-Artist, B-Athlete, I-Athlete, B-Politician, I-Politician, B-Cleric, I-Cleric, B-SportsManager, I-SportsManager, B-OtherPER, I-OtherPER\n"
        "Product (PROD): B-Clothing, I-Clothing, B-Vehicle, I-Vehicle, B-Food, I-Food, B-Drink, I-Drink, B-OtherPROD, I-OtherPROD\n"
        "Medical (MED): B-Medication/Vaccine, I-Medication/Vaccine, B-MedicalProcedure, I-MedicalProcedure, B-AnatomicalStructure, I-AnatomicalStructure, B-Symptom, I-Symptom, B-Disease, I-Disease\n"
        "O (Outside of any entity)\n"
    )

    prompt = f"Identify and label the named entities in the following {language} sentences with BIO tagging. The entities can be one of the following types:\n{entity_types}\n Examples:\n"

    for i, (sentence, annotation) in enumerate(zip(examples, annotations), 1):
        prompt += f"Sentence: {sentence}\n   Entities: {annotation} \n"

    prompt += f"\nNow, identify the named entities in the new {language} sentence following the same format:\n"

    return prompt

def generate_prediction(sentence, model, tokenizer, prompt_template):
    prompt = prompt_template + f"\nSentence: {sentence}\nEntities:"
    inputs = tokenizer.encode(prompt, return_tensors='pt')

    # Move input_ids to the same device as the model
    inputs = inputs.to(model.device)

    outputs = model.generate(inputs, max_length=2500, num_return_sequences=1)
    decoded_response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    print("DECODED_RESPONSE:")
    print(decoded_response)

    # Identify the start of the predicted tags
    start_index = decoded_response.find(f"Sentence: {sentence}\nEntities:") + len(f"Sentence: {sentence}\nEntities:")
    if start_index == -1:
        return []

    # Locate the end of the predicted tags
    end_index = decoded_response.find("Please", start_index)
    predicted_tags_str = decoded_response[start_index:end_index].strip() if end_index != -1 else decoded_response[start_index:].strip()
    predicted_tags = predicted_tags_str.split() if predicted_tags_str else []

    return predicted_tags

def clean_and_align_predicted_tags(predicted_tags, sentence_length):
    # Replace any non-tag elements with 'O' and truncate or pad to match sentence length
    cleaned_tags = [
        tag if tag.startswith('B-') or tag.startswith('I-') or tag == 'O' else 'O'
        for tag in predicted_tags
    ]

    return cleaned_tags[:sentence_length] + ['O'] * (sentence_length - len(cleaned_tags))

def evaluate_for_language(model, tokenizer, language, dataset, few_shot_data, prediction_filepath, score_filepath):
    # Prepare the initial part of the prompt with examples
    example_sentences = [" ".join(words) for words in few_shot_data['words']]
    example_annotations = [" ".join(tags) for tags in few_shot_data['tags']]
    prompt = create_ner_prompt(language, example_sentences, example_annotations)

    # List to store cleaned and aligned predicted tags
    cleaned_predicted_tags = []

    # Open the file for writing predictions
    with open(prediction_filepath, 'w', encoding='utf-8') as prediction_file:

        # Iterate over the test data
        for index, row in dataset.iterrows():
            sentence = " ".join(row['words'])
            generated_prediction = generate_prediction(sentence, model, tokenizer, prompt)
            aligned_tags = clean_and_align_predicted_tags(generated_prediction, len(row['words']))

            # Save aligned tags and reference tags for each sentence
            prediction_file.write(f"Sentence: {sentence}\n")
            prediction_file.write(f"Predicted Tags: {' '.join(aligned_tags)}\n")
            prediction_file.write(f"Reference Tags: {' '.join(row['tags'])}\n\n")

            cleaned_predicted_tags.append(aligned_tags)

    # Actual tags from the test data
    actual_tags = [tags for tags in dataset['tags']]

    # Calculate evaluation metrics
    precision = seqeval.metrics.precision_score(actual_tags, cleaned_predicted_tags)
    recall = seqeval.metrics.recall_score(actual_tags, cleaned_predicted_tags)
    f1_score = seqeval.metrics.f1_score(actual_tags, cleaned_predicted_tags)

    # Save the scores
    with open(score_filepath, 'w', encoding='utf-8') as score_file:
        scores = {
            'Precision': precision,
            'Recall': recall,
            'F1-Score': f1_score
        }
        score_file.write(json.dumps(scores, indent=4))

    print(f"Precision: {precision}, Recall: {recall}, F1-Score: {f1_score}")

def get_examples_and_sample(dataset, few_shot_size, sample_size):
    # sample the dataset for the few shot examples and remove them from the dataset
    few_shot_data = dataset.sample(n=few_shot_size, random_state=16)
    dataset = dataset.drop(few_shot_data.index)
    # sample the remainder of the dataset for the sample data
    sample_data = dataset.sample(n=sample_size, random_state=16)

    return few_shot_data, sample_data

if __name__ == '__main__':
    FEW_SHOT_SIZE = 5
    SAMPLE_SIZE = 300

    folder_path = '/home/rkt23/CPSC_488/CPSC_488_Data/'

    # Filenames

    # Bangla Data
    bn_test_file_path = folder_path + 'bn_test.conll'
    bn_test_ner_data = load_ner_data(bn_test_file_path)

    # Farsi Data
    fa_test_file_path = folder_path + 'fa_test.conll'
    fa_test_ner_data = load_ner_data(fa_test_file_path)

    # Hindi Data
    hi_test_file_path = folder_path + 'hi_test.conll'
    hi_test_ner_data = load_ner_data(hi_test_file_path)

    # Portuguese Data
    pt_test_file_path = folder_path + 'pt_test.conll'
    pt_test_ner_data = load_ner_data(pt_test_file_path)

    # Italian Data
    it_test_file_path = folder_path + 'it_test.conll'
    it_test_ner_data = load_ner_data(it_test_file_path)

    # Ukrainian Data
    uk_test_file_path = folder_path + 'uk_test.conll'
    uk_test_ner_data = load_ner_data(uk_test_file_path)

    # English Data
    en_test_file_path = folder_path + 'en_test.conll'
    en_test_ner_data = load_ner_data(en_test_file_path)

    # Bangla Sample
    bn_test_ner_data_few_shot, bn_test_ner_data_sample = get_examples_and_sample(bn_test_ner_data, FEW_SHOT_SIZE, SAMPLE_SIZE)

    # Farsi Sample
    fa_test_ner_data_few_shot, fa_test_ner_data_sample = get_examples_and_sample(fa_test_ner_data, FEW_SHOT_SIZE, SAMPLE_SIZE)

    # Hindi Sample
    hi_test_ner_data_few_shot, hi_test_ner_data_sample = get_examples_and_sample(hi_test_ner_data, FEW_SHOT_SIZE, SAMPLE_SIZE)

    # Portuguese Sample
    pt_test_ner_data_few_shot, pt_test_ner_data_sample = get_examples_and_sample(pt_test_ner_data, FEW_SHOT_SIZE, SAMPLE_SIZE)

    # Italian Sample
    it_test_ner_data_few_shot, it_test_ner_data_sample = get_examples_and_sample(it_test_ner_data, FEW_SHOT_SIZE, SAMPLE_SIZE)

    # Ukrainian Sample
    uk_test_ner_data_few_shot, uk_test_ner_data_sample = get_examples_and_sample(uk_test_ner_data, FEW_SHOT_SIZE, SAMPLE_SIZE)

    # English Sample
    en_test_ner_data_few_shot, en_test_ner_data_sample = get_examples_and_sample(en_test_ner_data, FEW_SHOT_SIZE, SAMPLE_SIZE)

    # Load the LLaMA model
    model_name = "meta-llama/Llama-2-7b-chat-hf"

    tokenizer = AutoTokenizer.from_pretrained(model_name, token="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")
    model = AutoModelForCausalLM.from_pretrained(model_name, token="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", device_map = 'auto')

    print("ENGLISH")
    en_prediction_filepath = folder_path + "en_cleaned_predicted_tags_100.txt"
    en_score_filepath = folder_path + "en_score.txt"
    evaluate_for_language(model, tokenizer, "English", en_test_ner_data_sample, en_test_ner_data_few_shot, en_prediction_filepath, en_score_filepath)
    print()

    print("PORTUGUESE")
    pt_prediction_filepath = folder_path + "pt_cleaned_predicted_tags_100.txt"
    pt_score_filepath = folder_path + "pt_score.txt"
    evaluate_for_language(model, tokenizer, "Portuguese", pt_test_ner_data_sample, pt_test_ner_data_few_shot, pt_prediction_filepath, pt_score_filepath)
    print()

    print("ITALIAN")
    it_prediction_filepath = folder_path + "it_cleaned_predicted_tags_100.txt"
    it_score_filepath = folder_path + "it_score.txt"
    evaluate_for_language(model, tokenizer, "Italian", it_test_ner_data_sample, it_test_ner_data_few_shot, it_prediction_filepath, it_score_filepath)
    print()

    print("UKRAINIAN")
    uk_prediction_filepath = folder_path + "uk_cleaned_predicted_tags_100.txt"
    uk_score_filepath = folder_path + "uk_score.txt"
    evaluate_for_language(model, tokenizer, "Ukrainian", uk_test_ner_data_sample, uk_test_ner_data_few_shot, uk_prediction_filepath, uk_score_filepath)
    print()