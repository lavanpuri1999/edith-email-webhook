"""Email filtering configuration for webhook notifications"""

# Gmail filters to apply to incoming push notifications
# Only emails matching these filters will be processed
WEBHOOK_EMAIL_FILTERS = [
    "is:important",
    "is:starred",
    "category:personal",
    "category:updates"
]

# Map Gmail query filters to label IDs that indicate a match
# These are the label IDs that Gmail uses internally
FILTER_LABEL_MAP = {
    "is:important": ["IMPORTANT"],
    "is:starred": ["STARRED"],
    "category:personal": ["CATEGORY_PERSONAL"],
    "category:updates": ["CATEGORY_UPDATES"]
}


def message_matches_filters(message_data: dict) -> bool:
    """
    Check if a Gmail message matches any of the configured filters
    
    Args:
        message_data: Gmail API message response with labelIds field
        
    Returns:
        True if message matches any filter, False otherwise
    """
    label_ids = message_data.get("labelIds", [])
    
    # Check if message matches any of the filters
    for filter_query in WEBHOOK_EMAIL_FILTERS:
        required_labels = FILTER_LABEL_MAP.get(filter_query, [])
        
        # If any required label is present, message matches this filter
        if any(label in label_ids for label in required_labels):
            return True
    
    return False

