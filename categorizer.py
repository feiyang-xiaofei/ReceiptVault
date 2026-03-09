CATEGORIES = [
    'Food & Dining',
    'Transport',
    'Software & Tech',
    'Office Supplies',
    'Utilities',
    'Entertainment',
    'Healthcare',
    'Other',
]

KEYWORD_MAP = {
    'Food & Dining': [
        'starbucks', 'mcdonald', 'burger', 'pizza', 'restaurant', 'cafe', 'coffee',
        'doordash', 'grubhub', 'uber eats', 'ubereats', 'chipotle', 'subway',
        'wendy', 'taco', 'bakery', 'diner', 'bistro', 'grill', 'sushi',
        'thai food', 'chinese food', 'indian food', 'mexican food', 'deli',
        'whole foods', 'trader joe', 'kroger', 'safeway', 'publix', 'aldi',
        'grocery', 'supermarket', 'food', 'dining', 'lunch', 'dinner', 'breakfast',
        'panera', 'chick-fil-a', 'popeyes', 'kfc', 'domino', 'papa john',
        'dunkin', 'peet', 'tim horton', 'five guys', 'shake shack',
    ],
    'Transport': [
        'uber', 'lyft', 'taxi', 'cab fare', 'gas station', 'shell', 'chevron',
        'bp ', 'exxon', 'mobil', 'parking', 'toll', 'transit', 'metro', 'bus',
        'airline', 'delta', 'united airline', 'american air', 'southwest',
        'jetblue', 'spirit air', 'amtrak', 'hertz', 'avis', 'enterprise',
        'rental car', 'fuel', 'gasoline', 'petrol', 'mileage', 'flight',
    ],
    'Software & Tech': [
        'github', 'aws', 'amazon web', 'google cloud', 'azure', 'digitalocean',
        'heroku', 'netlify', 'vercel', 'adobe', 'microsoft 365', 'apple',
        'jetbrains', 'slack', 'zoom', 'notion', 'figma', 'canva',
        'dropbox', 'software', 'saas', 'subscription', 'domain', 'hosting',
        'godaddy', 'namecheap', 'cloudflare', 'openai', 'chatgpt',
        'stripe', 'twilio', 'sendgrid', 'mailchimp', 'shopify',
    ],
    'Office Supplies': [
        'staples', 'office depot', 'officemax', 'paper', 'ink cartridge',
        'toner', 'printer', 'pen', 'notebook', 'binder', 'envelope',
        'stamp', 'postage', 'usps', 'fedex', 'ups', 'shipping', 'label',
        'desk', 'chair', 'monitor', 'keyboard', 'mouse', 'cable',
    ],
    'Utilities': [
        'electric', 'water bill', 'gas bill', 'internet', 'comcast', 'at&t',
        'verizon', 'tmobile', 't-mobile', 'sprint', 'phone bill', 'utility',
        'power company', 'energy', 'sewer', 'waste management', 'xfinity',
        'spectrum', 'cox', 'centurylink', 'frontier',
    ],
    'Entertainment': [
        'netflix', 'spotify', 'hulu', 'disney+', 'hbo', 'youtube premium',
        'cinema', 'movie', 'theater', 'theatre', 'concert', 'ticket',
        'ticketmaster', 'stubhub', 'steam', 'playstation', 'xbox',
        'nintendo', 'game', 'audible', 'kindle', 'book', 'magazine',
        'apple music', 'amazon prime', 'twitch',
    ],
    'Healthcare': [
        'pharmacy', 'cvs', 'walgreens', 'rite aid', 'hospital', 'clinic',
        'doctor', 'dentist', 'optometrist', 'medical', 'health', 'prescription',
        'rx ', 'lab', 'urgent care', 'insurance', 'copay', 'deductible',
        'therapy', 'counseling', 'vitamin', 'supplement',
    ],
}


def categorize_receipt(vendor_name, raw_text, db_corrections=None):
    """
    Categorize a receipt using 3-tier priority:
    1. User corrections from DB
    2. Keyword scoring
    3. Default to 'Other'
    """
    search_text = f"{vendor_name} {raw_text}".lower()

    # Tier 1: Check learned corrections
    if db_corrections:
        for pattern, category in db_corrections.items():
            if pattern.lower() in search_text:
                return category

    # Tier 2: Keyword scoring — count matches per category
    scores = {cat: 0 for cat in CATEGORIES}
    for category, keywords in KEYWORD_MAP.items():
        for keyword in keywords:
            if keyword in search_text:
                scores[category] += 1

    best_category = max(scores, key=scores.get)
    if scores[best_category] > 0:
        return best_category

    # Tier 3: Default
    return 'Other'
