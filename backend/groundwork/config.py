"""Tunable settings. Change them here, not in the modules."""

# chunking
CHUNK_TOKENS = 500  # estimated from word count, so treat it as "about 500"
CHUNK_OVERLAP_TOKENS = 75  # only used when a long section has to be cut mid-text
TOKENS_PER_WORD = 1.3  # rough English average, close enough for sizing chunks
HEADING_MAX_WORDS = 8
