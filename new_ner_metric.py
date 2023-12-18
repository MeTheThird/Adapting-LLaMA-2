"""
Takes in the names of the prediction vs. reference tag files output by one of the main llama_ner
python scripts, and evaluates the model output using our own custom NER evaluation metric, which is
the accuracy of the generated entity tags irrespective of position (one metric includes the outside
of entity set tag, and another excludes it), averaged across all test sentences for a given
language.
"""

import sys

def eval_and_write_new_ner_metric(filename):
    # given an input filename as described above, evaluates the model output with the hit rate by
    # BIO tag classification, both including and excluding the O tag

    sentence_str = "Sentence: "
    prediction_str = "Predicted Tags: "
    reference_str = "Reference Tags: "

    num_correct = 0
    num_correct_excluding_o = 0
    total_tokens_excluding_o = 0
    total_tokens = 0
    with open(filename, 'r', encoding='utf-8') as instream:
        prediction_dict = {}

        for line in instream:
            if line.startswith(sentence_str):
                continue

            elif line.startswith(prediction_str):
                for predicted_tag in line[len(prediction_str):].split(" "):
                    if predicted_tag not in prediction_dict:
                        prediction_dict[predicted_tag] = 0
                    prediction_dict[predicted_tag] += 1

            elif line.startswith(reference_str):
                for ref_tag in line[len(reference_str):].split(" "):
                    if ref_tag in prediction_dict and prediction_dict[ref_tag] > 0:
                        num_correct += 1
                        prediction_dict[ref_tag] -= 1

                        if ref_tag != "O":
                            num_correct_excluding_o += 1
                    total_tokens += 1

                    if ref_tag != "O":
                        total_tokens_excluding_o += 1

                prediction_dict.clear()

    with open(filename[:2] + "_custom_ner_score_sample_every.txt", 'w') as outstream:
        outstream.write(f"Token Accuracy Score Including O: {num_correct / total_tokens}\n")
        outstream.write(f"Token Accuracy Score Excluding O: {num_correct_excluding_o / total_tokens_excluding_o}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for filename in sys.argv[1:]:
            eval_and_write_new_ner_metric(filename)
