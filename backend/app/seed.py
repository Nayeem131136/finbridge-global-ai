"""Sample university directory. Names, countries and cities only (public facts).
It contains NO tuition fees, deadlines or payment/bank details; users must verify those with the university."""
from . import db

UNIVERSITIES = [
 ("University of Oxford","GB","Oxford"),("University of Cambridge","GB","Cambridge"),("Imperial College London","GB","London"),
 ("University of Manchester","GB","Manchester"),("University of Edinburgh","GB","Edinburgh"),("University of Glasgow","GB","Glasgow"),
 ("Massachusetts Institute of Technology","US","Cambridge, MA"),("Stanford University","US","Stanford, CA"),("University of Texas at Dallas","US","Richardson, TX"),
 ("Arizona State University","US","Tempe, AZ"),("Purdue University","US","West Lafayette, IN"),("University of Toronto","CA","Toronto"),
 ("University of British Columbia","CA","Vancouver"),("McGill University","CA","Montreal"),("University of Waterloo","CA","Waterloo"),
 ("University of Melbourne","AU","Melbourne"),("University of Sydney","AU","Sydney"),("Monash University","AU","Melbourne"),
 ("University of Queensland","AU","Brisbane"),("Technical University of Munich","DE","Munich"),("RWTH Aachen University","DE","Aachen"),
 ("Heidelberg University","DE","Heidelberg"),("Tsinghua University","CN","Beijing"),("Peking University","CN","Beijing"),
 ("Shenzhen University","CN","Shenzhen"),("Southern University of Science and Technology","CN","Shenzhen"),("Zhejiang University","CN","Hangzhou"),
 ("University of Malaya","MY","Kuala Lumpur"),("Universiti Teknologi Malaysia","MY","Johor Bahru"),("National University of Singapore","SG","Singapore"),
 ("Nanyang Technological University","SG","Singapore"),("University of Tokyo","JP","Tokyo"),("Kyoto University","JP","Kyoto"),
 ("Indian Institute of Technology Delhi","IN","New Delhi"),("University of Dhaka","BD","Dhaka"),("Khalifa University","AE","Abu Dhabi"),
]


def seed_universities() -> int:
    with db.tx() as c:
        for n, co, city in UNIVERSITIES:
            c.execute("INSERT OR IGNORE INTO universities(name, country, city) VALUES (?,?,?)", (n, co, city))
    return len(UNIVERSITIES)


# Directory entries only: names, providers and official websites. NO amounts, eligibility or deadlines are stated
# (those change every year and must be verified on the official site).
SCHOLARSHIPS = [
    ("Chevening Scholarships", "UK Government (FCDO)", "United Kingdom", "Master's", "https://www.chevening.org/"),
    ("Commonwealth Scholarships", "Commonwealth Scholarship Commission", "United Kingdom", "Master's / PhD", "https://cscuk.fcdo.gov.uk/"),
    ("DAAD Scholarships", "German Academic Exchange Service", "Germany", "Master's / PhD", "https://www.daad.de/en/"),
    ("Erasmus Mundus Joint Masters", "European Commission", "Multiple", "Master's", "https://erasmus-plus.ec.europa.eu/"),
    ("Chinese Government Scholarship (CSC)", "China Scholarship Council", "China", "All levels", "https://www.campuschina.org/"),
    ("Fulbright Program", "U.S. Department of State", "United States", "Master's / PhD", "https://fulbrightprogram.org/"),
]


def seed_scholarships() -> int:
    with db.tx() as c:
        for n, p, d, lv, u in SCHOLARSHIPS:
            c.execute("INSERT OR IGNORE INTO scholarships(name, provider, destination, level, url) VALUES (?,?,?,?,?)", (n, p, d, lv, u))
    return len(SCHOLARSHIPS)
