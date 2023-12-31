# -*- coding: utf-8 -*-
"""
Generates NER output as detailed in the README using our more detailed prompting strategy with 10
few shot examples that are randomly sampled at the beginning and then remain constant across all
of the test sentences.
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

    prompt = f"For the following sequences of words in the {language} sentences, generate the appropriate sequence of BIO tags, each tag corresponding with each word in a sentence. Indicate the end of the generated sequence with a ##### symbol. ##### means that the sequence of BIO Tags for the corresponding sentence has ended. Each entity type is marked as 'B-' (beginning), 'I-' (inside), or 'O' (outside). Types include Location (LOC), Creative Work (CW), Group (GRP), Person (PER), Product (PROD), and Medical (MED). Here are all possible BIO Tags:\n{entity_types}\n Here are some examples:\n"

    for i, (sentence, annotation) in enumerate(zip(examples, annotations), 1):
        prompt += f"Sentence: {sentence}\n   Sequence of BIO Tags: {annotation} #####\n"

    prompt += f"\nNow, using the same format as the examples, generate a sequence of BIO tags for the following sentence with each tag corresponding with each word in the new {language} sentence:\n"

    return prompt

def generate_prediction(sentence, model, tokenizer, prompt_template, decoded_response_filepath):
    prompt = prompt_template + f"\nSentence: {sentence}\nSequence of BIO Tags:"
    inputs = tokenizer.encode(prompt, return_tensors='pt')

    # Move input_ids to the same device as the model
    inputs = inputs.to(model.device)

    outputs = model.generate(inputs, max_length=2500, num_return_sequences=1)
    decoded_response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    print("DECODED RESPONSE: ")
    print(decoded_response)
    print("/////////////////////////\n\n")

    # Open the file for writing predictions
    with open(decoded_response_filepath, 'w', encoding='utf-8') as decoded_response_file:
        decoded_response_file.write(f"START OF DECODED RESPONSE \n\n")
        decoded_response_file.write(decoded_response)
        decoded_response_file.write(f"END OF DECODED RESPONSE \n\n\n")

    # Identify the start of the predicted tags
    start_index = decoded_response.find(f"Sentence: {sentence}\nSequence of BIO Tags:") + len(f"Sentence: {sentence}\nSequence of BIO Tags:")
    if start_index == -1:
        return []

    # Locate the end of the predicted tags
    end_index = decoded_response.find("#####", start_index)
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

def evaluate_for_language(model, tokenizer, language, dataset, few_shot_data, prediction_filepath, score_filepath, decoded_response_filepath):
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
            generated_prediction = generate_prediction(sentence, model, tokenizer, prompt, decoded_response_filepath)
            aligned_tags = clean_and_align_predicted_tags(generated_prediction, len(row['words']))

            # Save aligned tags and reference tags for each sentence
            prediction_file.write(f"Sentence: {sentence}\n")
            prediction_file.write(f"Predicted Tags: {' '.join(aligned_tags)}\n")
            prediction_file.write(f"Reference Tags: {' '.join(row['tags'])}\n\n")

            print("ALIGNED TAGS: ", aligned_tags)

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
    FEW_SHOT_SIZE = 10
    SAMPLE_SIZE = 300

    folder_path = 'INSERT_FOLDER_PATH_HERE'

    # Filenames

    # English Data
    en_test_file_path = folder_path + 'en_test.conll'
    en_test_ner_data = load_ner_data(en_test_file_path)

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

    # English Sample
    en_test_ner_data_few_shot, en_test_ner_data_sample = get_examples_and_sample(en_test_ner_data, FEW_SHOT_SIZE, SAMPLE_SIZE)

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

    # Load the LLaMA model
    model_name = "meta-llama/Llama-2-7b-chat-hf"

    tokenizer = AutoTokenizer.from_pretrained(model_name, token="INSERT_TOKEN_HERE")
    model = AutoModelForCausalLM.from_pretrained(model_name, token="INSERT_TOKEN_HERE", device_map = 'auto')

    print("ENGLISH")
    en_prediction_filepath = folder_path + "en_predicted_vs_reference_tags.txt"
    en_score_filepath = folder_path + "en_evaluation_scores.json"
    en_decoded_filepath = folder_path + "en_decoded_responses.txt"
    evaluate_for_language(model, tokenizer, "English", en_test_ner_data_sample, en_test_ner_data_few_shot, en_prediction_filepath, en_score_filepath, en_decoded_filepath)
    print()

    print("BANGLA")
    bn_prediction_filepath = folder_path + "bn_predicted_vs_reference_tags.txt"
    bn_score_filepath = folder_path + "bn_evaluation_scores.json"
    bn_decoded_filepath = folder_path + "bn_decoded_responses.txt"
    evaluate_for_language(model, tokenizer, "Bangla", bn_test_ner_data_sample, bn_test_ner_data_few_shot, bn_prediction_filepath, bn_score_filepath, bn_decoded_filepath)
    print()

    print("FARSI")
    fa_prediction_filepath = folder_path + "fa_predicted_vs_reference_tags.txt"
    fa_score_filepath = folder_path + "fa_evaluation_scores.json"
    fa_decoded_filepath = folder_path + "fa_decoded_responses.txt"
    evaluate_for_language(model, tokenizer, "Farsi", fa_test_ner_data_sample, fa_test_ner_data_few_shot, fa_prediction_filepath, fa_score_filepath, fa_decoded_filepath)
    print()

    print("HINDI")
    hi_prediction_filepath = folder_path + "hi_predicted_vs_reference_tags.txt"
    hi_score_filepath = folder_path + "hi_evaluation_scores.json"
    hi_decoded_filepath = folder_path + "hi_decoded_responses.txt"
    evaluate_for_language(model, tokenizer, "Hindi", hi_test_ner_data_sample, hi_test_ner_data_few_shot, hi_prediction_filepath, hi_score_filepath, hi_decoded_filepath)
    print()

    print("PORTUGUESE")
    pt_prediction_filepath = folder_path + "pt_predicted_vs_reference_tags.txt"
    pt_score_filepath = folder_path + "pt_evaluation_scores.json"
    pt_decoded_filepath = folder_path + "pt_decoded_responses.txt"
    evaluate_for_language(model, tokenizer, "Portuguese", pt_test_ner_data_sample, pt_test_ner_data_few_shot, pt_prediction_filepath, pt_score_filepath, pt_decoded_filepath)
    print()

    print("ITALIAN")
    it_prediction_filepath = folder_path + "it_predicted_vs_reference_tags.txt"
    it_score_filepath = folder_path + "it_evaluation_scores.json"
    it_decoded_filepath = folder_path + "it_decoded_responses.txt"
    evaluate_for_language(model, tokenizer, "Italian", it_test_ner_data_sample, it_test_ner_data_few_shot, it_prediction_filepath, it_score_filepath, it_decoded_filepath)
    print()

    print("UKRAINIAN")
    uk_prediction_filepath = folder_path + "uk_predicted_vs_reference_tags.txt"
    uk_score_filepath = folder_path + "uk_evaluation_scores.json"
    uk_decoded_filepath = folder_path + "uk_decoded_responses.txt"
    evaluate_for_language(model, tokenizer, "Ukrainian", uk_test_ner_data_sample, uk_test_ner_data_few_shot, uk_prediction_filepath, uk_score_filepath, uk_decoded_filepath)
    print()
