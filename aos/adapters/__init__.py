"""Data adapters for AOS harnesses.

File-based adapters that read JSON data from venture directories
and inject context into agent prompts.
"""

from aos.adapters.file_adapter import FileDataAdapter, load_venture_data

__all__ = ["FileDataAdapter", "load_venture_data"]
