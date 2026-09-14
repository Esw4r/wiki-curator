"""
Curated test claims with ground-truth labels for experiments.

Each claim is marked as True or False. This dataset is used by the
ExperimentRunner to evaluate system accuracy under different conditions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TestClaim:
    """A single test claim with its ground truth."""
    claim: str
    is_true: bool
    category: str  # e.g., "science", "history", "geography", "tech", "culture"


# ── True Claims (verifiable facts) ──────────────────────────────────────

TRUE_CLAIMS = [
    TestClaim("The Eiffel Tower was completed in 1889.", True, "history"),
    TestClaim("Python was created by Guido van Rossum.", True, "tech"),
    TestClaim("Water boils at 100 degrees Celsius at sea level.", True, "science"),
    TestClaim("The Great Wall of China is visible from space with the naked eye is a common myth.", True, "culture"),
    TestClaim("Albert Einstein developed the theory of general relativity.", True, "science"),
    TestClaim("Tokyo is the capital of Japan.", True, "geography"),
    TestClaim("The human body has 206 bones in adulthood.", True, "science"),
    TestClaim("The Amazon River is the largest river by discharge volume.", True, "geography"),
    TestClaim("Linux was created by Linus Torvalds in 1991.", True, "tech"),
    TestClaim("The speed of light in a vacuum is approximately 299,792 km/s.", True, "science"),
    TestClaim("Shakespeare wrote Hamlet around 1600.", True, "culture"),
    TestClaim("The Pacific Ocean is the largest ocean on Earth.", True, "geography"),
    TestClaim("DNA was first identified by Friedrich Miescher in 1869.", True, "science"),
    TestClaim("The first iPhone was released in 2007.", True, "tech"),
    TestClaim("Mount Everest is the tallest mountain above sea level.", True, "geography"),
    TestClaim("The Mona Lisa was painted by Leonardo da Vinci.", True, "culture"),
    TestClaim("Oxygen makes up about 21% of Earth's atmosphere.", True, "science"),
    TestClaim("The World Wide Web was invented by Tim Berners-Lee in 1989.", True, "tech"),
    TestClaim("Brazil is the largest country in South America.", True, "geography"),
    TestClaim("The French Revolution began in 1789.", True, "history"),
    TestClaim("Photosynthesis converts carbon dioxide and water into glucose and oxygen.", True, "science"),
    TestClaim("JavaScript was created by Brendan Eich in 1995.", True, "tech"),
    TestClaim("The Sahara is the largest hot desert in the world.", True, "geography"),
    TestClaim("Penicillin was discovered by Alexander Fleming in 1928.", True, "science"),
    TestClaim("The Berlin Wall fell in November 1989.", True, "history"),
    TestClaim("Mars is the fourth planet from the Sun.", True, "science"),
    TestClaim("The Git version control system was created by Linus Torvalds.", True, "tech"),
    TestClaim("Australia is both a country and a continent.", True, "geography"),
    TestClaim("The periodic table was created by Dmitri Mendeleev.", True, "science"),
    TestClaim("The Titanic sank in April 1912.", True, "history"),
]

# ── False Claims (plausible but incorrect) ───────────────────────────────

FALSE_CLAIMS = [
    TestClaim("The Eiffel Tower was completed in 1920.", False, "history"),
    TestClaim("Python was created by James Gosling.", False, "tech"),
    TestClaim("Water boils at 90 degrees Celsius at sea level.", False, "science"),
    TestClaim("Albert Einstein developed quantum mechanics.", False, "science"),
    TestClaim("Beijing is the capital of Japan.", False, "geography"),
    TestClaim("The human body has 305 bones in adulthood.", False, "science"),
    TestClaim("The Nile River is the largest river by discharge volume.", False, "geography"),
    TestClaim("Linux was created by Richard Stallman in 1985.", False, "tech"),
    TestClaim("The speed of light is approximately 150,000 km/s.", False, "science"),
    TestClaim("Shakespeare wrote Hamlet in 1650.", False, "culture"),
    TestClaim("The Atlantic Ocean is the largest ocean on Earth.", False, "geography"),
    TestClaim("DNA was first identified by Watson and Crick in 1953.", False, "science"),
    TestClaim("The first iPhone was released in 2005.", False, "tech"),
    TestClaim("K2 is the tallest mountain above sea level.", False, "geography"),
    TestClaim("The Mona Lisa was painted by Michelangelo.", False, "culture"),
    TestClaim("Oxygen makes up about 78% of Earth's atmosphere.", False, "science"),
    TestClaim("The World Wide Web was invented by Bill Gates.", False, "tech"),
    TestClaim("Argentina is the largest country in South America.", False, "geography"),
    TestClaim("The French Revolution began in 1812.", False, "history"),
    TestClaim("JavaScript was created by Guido van Rossum.", False, "tech"),
    TestClaim("The Gobi is the largest hot desert in the world.", False, "geography"),
    TestClaim("Penicillin was discovered by Louis Pasteur in 1895.", False, "science"),
    TestClaim("The Berlin Wall fell in 1991.", False, "history"),
    TestClaim("Venus is the fourth planet from the Sun.", False, "science"),
    TestClaim("Git was created by Dennis Ritchie.", False, "tech"),
    TestClaim("The periodic table was created by Isaac Newton.", False, "science"),
    TestClaim("The Titanic sank in 1915.", False, "history"),
    TestClaim("Photosynthesis produces carbon dioxide and water.", False, "science"),
    TestClaim("Mars is the third planet from the Sun.", False, "science"),
    TestClaim("The Great Pyramid of Giza was built in 500 AD.", False, "history"),
]

# ── Combined ─────────────────────────────────────────────────────────────

ALL_CLAIMS = TRUE_CLAIMS + FALSE_CLAIMS


def get_claims_subset(
    n: int = 10,
    balanced: bool = True,
) -> list[TestClaim]:
    """
    Get a subset of test claims.

    Args:
        n: Total number of claims to return.
        balanced: If True, return equal true and false claims.

    Returns:
        A list of TestClaim objects.
    """
    if balanced:
        half = n // 2
        true_subset = TRUE_CLAIMS[:half]
        false_subset = FALSE_CLAIMS[:half]
        # Interleave for variety
        result = []
        for t, f in zip(true_subset, false_subset):
            result.append(t)
            result.append(f)
        # If n is odd, add one more true claim
        if n % 2 == 1 and len(TRUE_CLAIMS) > half:
            result.append(TRUE_CLAIMS[half])
        return result[:n]
    else:
        return ALL_CLAIMS[:n]
