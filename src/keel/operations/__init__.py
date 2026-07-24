"""Operations — durable truth (SQLite), incidents, and order-intent records.

This package owns structured persistence and operational safety records. It does
not import broker clients or LLM providers; it stores what the runtime hands it.
"""
