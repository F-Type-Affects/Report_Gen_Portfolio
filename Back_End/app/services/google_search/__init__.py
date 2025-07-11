"""
Google Search Service Package

Provides Google Custom Search functionality for finding AHJ building code
amendments and related documentation.
"""

from .google_search_service import (
    GoogleSearchService,
    SearchResult,
    perform_google_search
)

__all__ = [
    'GoogleSearchService',
    'SearchResult',
    'perform_google_search'
]

# Package metadata
__version__ = '1.0.0'
__author__ = 'Lead Software Developer'