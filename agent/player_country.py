import re
EUROPE={"Albania","Austria","Belgium","Bosnia-Herzegovina","Bosnia and Herzegovina","Bulgaria","Croatia","Cyprus","Czech Republic","Czechoslovakia","Denmark","England","Estonia","Finland","France","Germany","Greece","Hungary","Iceland","Ireland","Italy","Kosovo","Latvia","Lithuania","Luxembourg","Malta","Montenegro","Netherlands","North Macedonia","Northern Ireland","Norway","Poland","Portugal","Romania","Russia","Scotland","Serbia","Slovakia","Slovenia","Soviet Union","Spain","Sweden","Switzerland","Turkey","Ukraine","Wales","Yugoslavia"}
AFRICA={"Algeria","Angola","Benin","Burkina Faso","Burundi","Cameroon","Cape Verde","Central African Republic","Chad","Congo","Cote d'Ivoire","DR Congo","Egypt","Equatorial Guinea","Eritrea","Ethiopia","Gabon","Gambia","The Gambia","Ghana","Guinea","Guinea-Bissau","Kenya","Liberia","Libya","Madagascar","Mali","Mauritania","Mauritius","Morocco","Mozambique","Namibia","Niger","Nigeria","Rwanda","Senegal","Sierra Leone","South Africa","Sudan","Tanzania","Togo","Tunisia","Uganda","Zambia","Zimbabwe"}
ASIA={"Afghanistan","Bahrain","China","Georgia","India","Indonesia","Iran","Iraq","Israel","Japan","Jordan","Kazakhstan","Kuwait","Kyrgyzstan","Lebanon","Malaysia","North Korea","Oman","Pakistan","Palestine","Philippines","Qatar","Saudi Arabia","South Korea","Syria","Tajikistan","Thailand","Turkmenistan","United Arab Emirates","Uzbekistan","Vietnam"}
N_AMERICA={"Antigua and Barbuda","Aruba","Bahamas","Barbados","Belize","Bermuda","Canada","Costa Rica","Cuba","Curacao","Curaçao","Dominica","Dominican Republic","El Salvador","Grenada","Guadeloupe","Guatemala","Guyana","Haiti","Honduras","Jamaica","Martinique","Mexico","Montserrat","Nicaragua","Panama","Puerto Rico","Saint Kitts and Nevis","Saint Lucia","Suriname","Trinidad and Tobago","United States","US Virgin Islands"}
S_AMERICA={"Argentina","Bolivia","Brazil","Chile","Colombia","Ecuador","Paraguay","Peru","Uruguay","Venezuela"}
OCEANIA={"Australia","Fiji","New Caledonia","New Zealand","Papua New Guinea","Samoa","Solomon Islands","Tahiti","Tonga","Vanuatu"}

def integer(v):
    try: return int(float(v))
    except: return 0

def season_year(s):
    m=re.match(r"(\d{2,4})",s or "")
    if not m: return None
    y=int(m.group(1))
    return 2000+y if y<40 else (1900+y if y<100 else y)

def clean_name(v):
    return re.sub(r" \(\d+\)$","",v or "").strip()

def first_country(v):
    parts=re.split(r"\s{2,}|\s*/\s*|,",v or "")
    n=(parts[0] if parts else "").strip()
    return {"Ireland":"Republic of Ireland","United States":"USA","Cote d'Ivoire":"Ivory Coast"}.get(n,n)

def continent(n):
    raw={"Republic of Ireland":"Ireland","USA":"United States","Ivory Coast":"Cote d'Ivoire","Türkiye":"Turkey","Korea":"South Korea","St. Kitts & Nevis":"Saint Kitts and Nevis","St. Lucia":"Saint Lucia"}.get(n,n)
    if raw in {"Armenia","Belarus","Faroe Islands","Jersey"}:return "Europe"
    if raw=="French Guiana":return "South America"
    if raw=="Seychelles":return "Africa"
    if raw in EUROPE:return "Europe"
    if raw in AFRICA:return "Africa"
    if raw in ASIA:return "Asia"
    if raw in N_AMERICA:return "North America"
    if raw in S_AMERICA:return "South America"
    if raw in OCEANIA:return "Oceania"
    return "Other"

def senior(team):
    t=team.lower()
    return not any(x in t for x in (" u18"," u19"," u20"," u21"," u23"," youth"," reserves"," ii"," b team"))


