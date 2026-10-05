"""Football nationality for players holding more than one citizenship, and canonical country names."""
import re
from source_utils import clean

CANONICAL = {'Ireland': 'Republic of Ireland', "Cote d'Ivoire": 'Ivory Coast', "Côte d'Ivoire": 'Ivory Coast', 'Korea': 'South Korea',
             'Korea, South': 'South Korea', 'United States': 'USA', 'Bosnia and Herzegovina': 'Bosnia-Herzegovina', 'Türkiye': 'Turkey', 'Curaçao': 'Curacao'}
ADJ = {'English': 'England', 'Welsh': 'Wales', 'Scottish': 'Scotland', 'Northern Irish': 'Northern Ireland', 'Irish': 'Republic of Ireland',
       'French': 'France', 'Dutch': 'Netherlands', 'German': 'Germany', 'Spanish': 'Spain', 'Portuguese': 'Portugal', 'Italian': 'Italy',
       'Belgian': 'Belgium', 'Jamaican': 'Jamaica', 'Nigerian': 'Nigeria', 'Ghanaian': 'Ghana', 'Ivorian': 'Ivory Coast', 'Senegalese': 'Senegal',
       'Moroccan': 'Morocco', 'Algerian': 'Algeria', 'Tunisian': 'Tunisia', 'Cameroonian': 'Cameroon', 'American': 'USA', 'Canadian': 'Canada',
       'Australian': 'Australia', 'New Zealand': 'New Zealand', 'South Korean': 'South Korea', 'Japanese': 'Japan', 'Swedish': 'Sweden',
       'Norwegian': 'Norway', 'Danish': 'Denmark', 'Finnish': 'Finland', 'Icelandic': 'Iceland', 'Polish': 'Poland', 'Czech': 'Czech Republic',
       'Slovak': 'Slovakia', 'Hungarian': 'Hungary', 'Croatian': 'Croatia', 'Serbian': 'Serbia', 'Bosnian': 'Bosnia-Herzegovina', 'Greek': 'Greece',
       'Turkish': 'Turkey', 'Swiss': 'Switzerland', 'Austrian': 'Austria', 'Albanian': 'Albania', 'Kosovan': 'Kosovo', 'Kosovar': 'Kosovo',
       'Montenegrin': 'Montenegro', 'Slovenian': 'Slovenia', 'Romanian': 'Romania', 'Bulgarian': 'Bulgaria', 'Ukrainian': 'Ukraine', 'Russian': 'Russia',
       'Brazilian': 'Brazil', 'Argentine': 'Argentina', 'Argentinian': 'Argentina', 'Uruguayan': 'Uruguay', 'Colombian': 'Colombia', 'Chilean': 'Chile',
       'Ecuadorian': 'Ecuador', 'Paraguayan': 'Paraguay', 'Venezuelan': 'Venezuela', 'Peruvian': 'Peru', 'Mexican': 'Mexico', 'Grenadian': 'Grenada',
       'Trinidadian': 'Trinidad and Tobago', 'Barbadian': 'Barbados', 'Guyanese': 'Guyana', 'Bermudian': 'Bermuda', 'Montserratian': 'Montserrat',
       'Kittitian': 'St. Kitts & Nevis', 'Zimbabwean': 'Zimbabwe', 'Zambian': 'Zambia', 'South African': 'South Africa', 'Kenyan': 'Kenya',
       'Ugandan': 'Uganda', 'Sierra Leonean': 'Sierra Leone', 'Liberian': 'Liberia', 'Gambian': 'The Gambia', 'Guinean': 'Guinea', 'Malian': 'Mali',
       'Burkinabé': 'Burkina Faso', 'Beninese': 'Benin', 'Togolese': 'Togo', 'Angolan': 'Angola', 'Cape Verdean': 'Cape Verde', 'Gabonese': 'Gabon',
       'Egyptian': 'Egypt', 'Libyan': 'Libya', 'Israeli': 'Israel', 'Iranian': 'Iran', 'Iraqi': 'Iraq', 'Cypriot': 'Cyprus', 'Maltese': 'Malta',
       'Gibraltarian': 'Gibraltar', 'Faroese': 'Faroe Islands', 'Estonian': 'Estonia', 'Latvian': 'Latvia', 'Lithuanian': 'Lithuania', 'Georgian': 'Georgia',
       'Armenian': 'Armenia', 'Belarusian': 'Belarus', 'Macedonian': 'North Macedonia', 'Filipino': 'Philippines', 'Thai': 'Thailand', 'Chinese': 'China',
       'Indian': 'India', 'Pakistani': 'Pakistan', 'Bangladeshi': 'Bangladesh', 'Haitian': 'Haiti', 'Cuban': 'Cuba', 'Honduran': 'Honduras',
       'Costa Rican': 'Costa Rica', 'Panamanian': 'Panama', 'Guatemalan': 'Guatemala', 'Curaçaoan': 'Curacao', 'Surinamese': 'Suriname',
       'Congolese': 'DR Congo', 'Equatoguinean': 'Equatorial Guinea', 'Bissau-Guinean': 'Guinea-Bissau', 'Tanzanian': 'Tanzania', 'Indonesian': 'Indonesia'}

def canonical(n):
    return CANONICAL.get(n, n)

def from_article(raw, citizenships):
    """(country, evidence) when Wikipedia says which of the player's citizenships he represents, else None."""
    held = {canonical(c) for c in citizenships}
    text = ' '.join(clean(p) for p in re.findall(r'<p\b[^>]*>.*?</p>', raw, re.S)[:4])
    names = '|'.join(sorted({re.escape(h) for h in held} | {'the ' + re.escape(h) for h in held}, key=len, reverse=True))
    rep = re.findall(r'\b(?:represents|represented|has represented|plays for|played for|has played for|was capped by|capped by)\s+(' + names + r')(?:\s+national(?: football)? team|\s+at (?:senior |full )?international level)', text)
    rep = {canonical(r.removeprefix('the ')) for r in rep}
    if len(rep) == 1: return rep.pop(), 'represents at international level (Wikipedia)'
    lead = re.search(r'\bis an? ((?:[A-Z][\w-]*\s){1,2})(?:former )?(?:professional |semi-professional |retired )?(?:association )?football', text)
    if lead:
        adj = lead[1].strip()
        country = ADJ.get(adj) or ADJ.get(adj.split()[-1])
        if country in held: return country, f'opening line "{adj}" footballer (Wikipedia)'
    return None
