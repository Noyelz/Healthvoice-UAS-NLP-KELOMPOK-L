from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from nltk.tokenize import word_tokenize
import nltk

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

context = "Halo nama saya Budi dan saya sakit batuk."
answer = "Budi"

reference = [word_tokenize(context.lower())]
candidate = word_tokenize(answer.lower())

chencherry = SmoothingFunction()

# Current implementation (Default weights are 0.25, 0.25, 0.25, 0.25)
score_default = sentence_bleu(reference, candidate, smoothing_function=chencherry.method1)
print(f"Candidate: {candidate}")
print(f"Default (4-gram) Score: {score_default}")

# Proposed Fix: BLEU-1 (Unigram only)
score_1 = sentence_bleu(reference, candidate, weights=(1, 0, 0, 0), smoothing_function=chencherry.method1)
print(f"BLEU-1 Score: {score_1}")

# Proposed Fix: BLEU-2 (Bigram)
score_2 = sentence_bleu(reference, candidate, weights=(0.5, 0.5, 0, 0), smoothing_function=chencherry.method1)
print(f"BLEU-2 Score: {score_2}")
