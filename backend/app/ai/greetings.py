"""Recognize standalone social turns without supplying canned responses."""

import unicodedata


def is_social_turn(question: str) -> bool:
    text = unicodedata.normalize("NFKC", question).casefold().strip()
    while text and unicodedata.category(text[-1]).startswith("P"):
        text = text[:-1].rstrip()
    text = " ".join(text.split())
    return text in {
        "hi", "hello", "hey", "hello there", "hey there",
        "good morning", "good afternoon", "good evening",
        "how are you", "how are you doing", "hi how are you", "hello how are you",
        "thanks", "thank you", "thank you so much", "you're welcome",
        "bye", "goodbye", "see you", "good night",
        "হাই", "হ্যালো", "নমস্কার", "শুভ সকাল", "শুভ সন্ধ্যা",
        "কেমন আছো", "কেমন আছেন", "তুমি কেমন আছো", "আপনি কেমন আছেন",
        "ধন্যবাদ", "অনেক ধন্যবাদ", "বিদায়", "শুভ রাত্রি",
        "আসসালামু আলাইকুম", "assalamu alaikum", "assalamualaikum", "salam",
        "kemon acho", "kemon achen", "dhonnobad",
    }
