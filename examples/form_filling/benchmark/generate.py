"""Generate the five benchmark forms: form.html, facts.json and expected.json in each subfolder.

Run from the repository root with uv run python -m examples.form_filling.benchmark.generate.
The output is deterministic. Edit a build_* function and run it again to change a form.
"""

import json
from pathlib import Path

DIRECTORY = Path(__file__).parent

STYLE = ("<style>body{max-width:60rem;margin:2rem auto;font:15px/1.4 system-ui}fieldset{display:grid;"
         "grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:.6rem;margin:.8rem 0}label{display:grid}"
         "[role=listbox]{border:1px solid #999;padding:.3rem}[role=option]{padding:.2rem .4rem;cursor:pointer}"
         "[role=option][aria-selected=true]{background:#cde}</style>")

COUNTRIES = ["Argentina", "Australia", "Austria", "Belgium", "Brazil", "Canada", "Chile", "China", "Colombia",
             "Denmark", "Egypt", "Finland", "France", "Germany", "Greece", "India", "Indonesia", "Ireland", "Italy",
             "Japan", "Jordan", "Kenya", "Lebanon", "Mexico", "Morocco", "Netherlands", "New Zealand", "Nigeria",
             "Norway", "Peru", "Poland", "Portugal", "South Africa", "South Korea", "Spain", "Sweden", "Switzerland",
             "Thailand", "Turkey", "United Kingdom", "United States", "Vietnam"]
PROVINCES = {"Canada": ["British Columbia", "Ontario", "Quebec"], "United States": ["California", "Texas"],
             "Germany": ["Bavaria", "Berlin"]}


def control(kind, id_, label, attrs=""):
    if kind == "textarea":
        return f'<label>{label}<textarea id="{id_}"></textarea></label>'
    return f'<label>{label}<input type="{kind}" id="{id_}"{attrs}></label>'


def dropdown(id_, label, options, *, multiple=False, disabled=False):
    items = ("" if multiple else "<option></option>") + "".join(f"<option>{o}</option>" for o in options)
    flags = (" multiple" if multiple else "") + (" disabled" if disabled else "")
    return f'<label>{label}<select id="{id_}"{flags}>{items}</select></label>'


def datalist(id_, label, list_id, options):
    return (f'<label>{label}<input id="{id_}" list="{list_id}"></label><datalist id="{list_id}">'
            + "".join(f'<option value="{o}">' for o in options) + "</datalist>")


def aria_combobox(id_, label, options):
    """A button that opens a popup list; the chosen option becomes the button text."""
    return (f'<span id="{id_}Label">{label}</span>'
            f'<button type="button" role="combobox" id="{id_}" aria-labelledby="{id_}Label" aria-controls="{id_}Menu" '
            f'aria-expanded="false" data-check data-combobox>Choose…</button>'
            f'<div role="listbox" id="{id_}Menu" hidden>'
            + "".join(f'<div role="option">{o}</div>' for o in options) + "</div>")


def aria_multilistbox(id_, label, options):
    return (f'<span id="{id_}Label">{label}</span>'
            f'<div role="listbox" id="{id_}" aria-labelledby="{id_}Label" aria-multiselectable="true" tabindex="0" '
            f'data-check data-multilistbox>'
            + "".join(f'<div role="option" aria-selected="false">{o}</div>' for o in options) + "</div>")


def fieldset(legend, *controls):
    return f"<fieldset><legend>{legend}</legend>{''.join(controls)}</fieldset>"


SCRIPT = """<script>
const PROVINCES = %s;
for (const el of document.querySelectorAll('[data-country]')) {
  const target = document.getElementById(el.dataset.country);
  el.onchange = () => {
    const items = PROVINCES[el.value] || [];
    target.innerHTML = '<option></option>' + items.map(i => `<option>${i}</option>`).join('');
    target.disabled = !items.length;
  };
}
for (const el of document.querySelectorAll('[data-enables]')) {
  el.onchange = () => { document.getElementById(el.dataset.enables).disabled = !el.checked; };
}
for (const box of document.querySelectorAll('[data-combobox]')) {
  const menu = document.getElementById(box.getAttribute('aria-controls'));
  box.onclick = () => { menu.hidden = false; box.setAttribute('aria-expanded', 'true'); };
  for (const option of menu.children) option.onclick = () => {
    for (const other of menu.children) other.setAttribute('aria-selected', String(other === option));
    box.textContent = option.textContent; menu.hidden = true; box.setAttribute('aria-expanded', 'false');
  };
}
for (const list of document.querySelectorAll('[data-multilistbox]')) {
  for (const option of list.children) option.onclick = () =>
    option.setAttribute('aria-selected', String(option.getAttribute('aria-selected') !== 'true'));
}
</script>""" % json.dumps(PROVINCES)


def build_job_application():
    sections = [
        fieldset("Applicant",
                 control("text", "name", "Full name"), control("email", "email", "Email"),
                 control("email", "email2", "Confirm email"), control("tel", "phone", "Phone"),
                 control("url", "linkedin", "LinkedIn profile"), control("url", "portfolio", "Portfolio website")),
        fieldset("Position",
                 dropdown("position", "Position applied for",
                          ["Backend Engineer", "Frontend Engineer", "Data Analyst", "Product Designer"]),
                 control("date", "start", "Earliest start date"),
                 control("number", "salary", "Desired annual salary (CAD)", ' min="0"'),
                 control("number", "years", "Years of professional experience", ' min="0"'),
                 dropdown("authorized", "Authorized to work in Canada", ["Yes", "No"]),
                 control("checkbox", "relocate", "Willing to relocate"),
                 datalist("source", "How did you hear about us?", "sources", ["LinkedIn", "Indeed", "A friend", "Other"])),
        fieldset("Experience",
                 control("text", "employer", "Current or most recent employer"),
                 control("text", "title", "Current or most recent job title"),
                 control("textarea", "cover", "Cover letter")),
    ]
    cover = ("I build dashboards that teams actually use. At Northwind I cut report turnaround from a week to a day "
             "by replacing hand-made spreadsheets with a shared data model.")
    facts = {
        "applicant full name": "Dalia Haddad", "applicant email": "dalia.haddad@example.com",
        "applicant phone": "+1 416 555 0133", "applicant linkedin profile": "https://linkedin.example/in/daliahaddad",
        "applicant portfolio website": "https://dalia.example.org", "position applied for": "Data Analyst",
        "earliest start date": "2026-12-01", "desired annual salary CAD": 95000,
        "years of professional experience": 6, "authorized to work in Canada": "Yes", "willing to relocate": True,
        "how the applicant heard about the job": "LinkedIn", "most recent employer": "Northwind Analytics",
        "most recent job title": "Senior Analyst", "cover letter": cover,
        # Decoys and extras
        "employer before Northwind": "Cedar Ridge Clinic", "job title before Northwind": "Analyst",
        "applicant nickname": "Dee", "applicant preferred pronouns": "she/her",
    }
    expected = {
        "name": "Dalia Haddad", "email": "dalia.haddad@example.com", "email2": "dalia.haddad@example.com",
        "phone": "+1 416 555 0133", "linkedin": "https://linkedin.example/in/daliahaddad",
        "portfolio": "https://dalia.example.org", "position": "Data Analyst", "start": "2026-12-01",
        "salary": "95000", "years": "6", "authorized": "Yes", "relocate": True, "source": "LinkedIn",
        "employer": "Northwind Analytics", "title": "Senior Analyst", "cover": cover,
    }
    return "Job application", sections, facts, expected


def build_medical_intake():
    sections = [
        fieldset("Patient",
                 control("text", "p_name", "Full name"), control("date", "p_dob", "Date of birth"),
                 control("email", "p_email", "Email"), control("tel", "p_phone", "Phone"),
                 dropdown("p_sex", "Sex", ["Female", "Male", "Other", "Prefer not to say"]),
                 dropdown("p_blood", "Blood type", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]),
                 control("number", "p_height", "Height (cm)"), control("number", "p_weight", "Weight (kg)"),
                 dropdown("p_allergies", "Known allergies",
                          ["Penicillin", "Latex", "Peanuts", "Shellfish", "Aspirin"], multiple=True),
                 control("textarea", "p_meds", "Current medications"),
                 control("checkbox", "p_smoker", "Smoker")),
        fieldset("Emergency contact",
                 control("text", "e_name", "Full name"),
                 dropdown("e_rel", "Relationship to patient", ["Spouse", "Parent", "Child", "Sibling", "Friend"]),
                 control("tel", "e_phone", "Phone"), control("email", "e_email", "Email")),
        fieldset("Primary physician",
                 control("text", "d_name", "Full name"), control("text", "d_clinic", "Clinic"),
                 control("tel", "d_phone", "Phone")),
        fieldset("Insurance",
                 control("checkbox", "i_has", "Patient has health insurance", ' data-enables="i_policy"'),
                 dropdown("i_provider", "Insurance provider", ["Sun Life", "Manulife", "Blue Cross", "Other"]),
                 control("text", "i_policy", "Policy number", " disabled"),
                 control("text", "i_group", "Group number")),
        fieldset("Consent",
                 control("checkbox", "c_treat", "I consent to treatment"),
                 control("checkbox", "c_share", "I consent to sharing my data with research partners")),
    ]
    meds = "Metformin 500 mg twice daily; Atorvastatin 20 mg nightly"
    facts = {
        "patient full name": "Omar Nakamura", "patient date of birth": "1979-11-02",
        "patient email": "omar.nakamura@example.com", "patient phone": "+1 604 555 0188", "patient sex": "Male",
        "patient blood type": "AB-", "patient height cm": 178, "patient weight kg": 81,
        "patient known allergies": ["Penicillin", "Shellfish"], "patient current medications": meds,
        "patient is a smoker": False,
        "emergency contact full name": "Yuki Nakamura", "emergency contact relationship to patient": "Spouse",
        "emergency contact phone": "+1 604 555 0190", "emergency contact email": "yuki.n@example.com",
        "primary physician full name": "Dr. Lena Moreau", "primary physician clinic": "Cedar Ridge Clinic",
        "primary physician phone": "+1 604 555 0101",
        "patient has health insurance": True, "insurance provider": "Manulife",
        "insurance policy number": "MNL-884201", "insurance group number": "G-5521",
        "patient consents to treatment": True, "patient consents to sharing data with research partners": False,
        # Decoys
        "patient former phone": "+1 604 555 0007", "patient previous physician": "Dr. Raj Patel",
        "patient childhood allergy, since outgrown": "Latex",
    }
    expected = {
        "p_name": "Omar Nakamura", "p_dob": "1979-11-02", "p_email": "omar.nakamura@example.com",
        "p_phone": "+1 604 555 0188", "p_sex": "Male", "p_blood": "AB-", "p_height": "178", "p_weight": "81",
        "p_allergies": ["Penicillin", "Shellfish"], "p_meds": meds, "p_smoker": False,
        "e_name": "Yuki Nakamura", "e_rel": "Spouse", "e_phone": "+1 604 555 0190", "e_email": "yuki.n@example.com",
        "d_name": "Dr. Lena Moreau", "d_clinic": "Cedar Ridge Clinic", "d_phone": "+1 604 555 0101",
        "i_has": True, "i_provider": "Manulife", "i_policy": "MNL-884201", "i_group": "G-5521",
        "c_treat": True, "c_share": False,
    }
    return "Medical intake", sections, facts, expected


def build_checkout():
    sections = [
        fieldset("Contact", control("email", "email", "Email"), control("tel", "phone", "Phone")),
        fieldset("Shipping address",
                 control("text", "s_name", "Full name"), control("text", "s_street", "Street address"),
                 control("text", "s_apt", "Apartment, suite, etc."), control("text", "s_city", "City"),
                 control("text", "s_postal", "Postal code"),
                 dropdown("s_country", "Country", list(PROVINCES)).replace('id="s_country"', 'id="s_country" data-country="s_province"'),
                 dropdown("s_province", "Province or state", [], disabled=True),
                 control("textarea", "s_notes", "Delivery instructions")),
        fieldset("Billing address",
                 control("checkbox", "b_same", "Billing address is the same as shipping"),
                 control("text", "b_name", "Full name"), control("text", "b_street", "Street address"),
                 control("text", "b_city", "City"), control("text", "b_postal", "Postal code"),
                 dropdown("b_country", "Country", list(PROVINCES)).replace('id="b_country"', 'id="b_country" data-country="b_province"'),
                 dropdown("b_province", "Province or state", [], disabled=True)),
        fieldset("Delivery",
                 aria_combobox("method", "Delivery method", ["Standard", "Express", "Overnight"]),
                 control("checkbox", "gift", "Gift wrap"), control("textarea", "gift_msg", "Gift message"),
                 control("text", "promo", "Promo code"), control("checkbox", "news", "Subscribe to the newsletter")),
        fieldset("Payment",
                 control("text", "card_name", "Cardholder name"), control("text", "card_no", "Card number"),
                 dropdown("exp_m", "Expiry month", [f"{m:02}" for m in range(1, 13)]),
                 dropdown("exp_y", "Expiry year", [str(y) for y in range(2026, 2033)]),
                 control("password", "cvv", "Security code")),
    ]
    facts = {
        "customer email": "priya.castillo@example.com", "customer phone": "+1 250 555 0144",
        "shipping recipient full name": "Priya Castillo", "shipping street address": "88 Lakeview Drive",
        "shipping city": "Kelowna", "shipping postal code": "V1Y 9P4", "shipping country": "Canada",
        "shipping province": "British Columbia", "delivery instructions": "Leave the parcel with the concierge.",
        "billing address is the same as shipping": False, "billing full name": "Arjun Castillo",
        "billing street address": "12 Rue Sainte-Anne", "billing city": "Québec", "billing postal code": "G1R 3X2",
        "billing country": "Canada", "billing province": "Quebec",
        "delivery method": "Express", "gift wrap": True, "gift message": "Happy birthday, Nia!",
        "subscribe to the newsletter": False,
        "cardholder name": "Arjun Castillo", "card number": "4111 1111 1111 1111",
        "card expiry month": "09", "card expiry year": "2029",
        # Decoys
        "previous shipping street address": "5 Old Mill Road", "previous shipping city": "Vernon",
        "card security code": "123",
    }
    expected = {
        "email": "priya.castillo@example.com", "phone": "+1 250 555 0144",
        "s_name": "Priya Castillo", "s_street": "88 Lakeview Drive", "s_apt": "", "s_city": "Kelowna",
        "s_postal": "V1Y 9P4", "s_country": "Canada", "s_province": "British Columbia",
        "s_notes": "Leave the parcel with the concierge.",
        "b_same": False, "b_name": "Arjun Castillo", "b_street": "12 Rue Sainte-Anne", "b_city": "Québec",
        "b_postal": "G1R 3X2", "b_country": "Canada", "b_province": "Quebec",
        "method": "Express", "gift": True, "gift_msg": "Happy birthday, Nia!", "promo": "", "news": False,
        "card_name": "Arjun Castillo", "card_no": "4111 1111 1111 1111", "exp_m": "09", "exp_y": "2029", "cvv": "",
    }
    return "Checkout", sections, facts, expected


def build_visa_application():
    visited = ["Australia", "Brazil", "Canada", "China", "Egypt", "France", "Germany", "India", "Italy", "Japan",
               "Mexico", "Morocco", "South Africa", "South Korea", "Spain", "Thailand", "Turkey",
               "United Kingdom", "United States", "Vietnam"]
    sections = [
        fieldset("Applicant",
                 control("text", "a_surname", "Surname"), control("text", "a_given", "Given names"),
                 control("date", "a_dob", "Date of birth"), dropdown("a_nat", "Nationality", COUNTRIES),
                 control("text", "a_passport", "Passport number"),
                 control("date", "a_issued", "Passport issue date"), control("date", "a_expiry", "Passport expiry date"),
                 control("email", "a_email", "Email"), control("tel", "a_phone", "Phone"),
                 control("text", "a_job", "Occupation"), control("text", "a_employer", "Employer"),
                 dropdown("a_purpose", "Purpose of visit", ["Tourism", "Business", "Study", "Family visit"]),
                 control("date", "a_arrive", "Intended arrival date"), control("date", "a_depart", "Intended departure date"),
                 control("textarea", "a_address", "Address during the stay"),
                 dropdown("a_visited", "Countries visited in the last five years", visited, multiple=True),
                 control("checkbox", "a_refused", "Previously refused a visa"),
                 control("checkbox", "a_record", "Criminal record")),
    ]
    for i in (1, 2, 3):
        sections.append(fieldset(
            f"Companion {i}",
            control("text", f"c{i}_surname", "Surname"), control("text", f"c{i}_given", "Given names"),
            control("date", f"c{i}_dob", "Date of birth"),
            dropdown(f"c{i}_rel", "Relationship to applicant", ["Spouse", "Child", "Parent", "Friend"]),
            control("text", f"c{i}_passport", "Passport number")))
    sections.append(fieldset("Sponsor in the destination country",
                             control("text", "s_name", "Full name"), control("tel", "s_phone", "Phone"),
                             control("textarea", "s_address", "Address")))
    sections.append(fieldset("Emergency contact",
                             control("text", "e_name", "Full name"), control("tel", "e_phone", "Phone")))
    facts = {
        "applicant surname": "Khoury", "applicant given names": "Rami Elias", "applicant date of birth": "1991-06-23",
        "applicant nationality": "Lebanon", "applicant passport number": "LR4482917",
        "applicant passport issue date": "2022-03-10", "applicant passport expiry date": "2032-03-09",
        "applicant email": "rami.khoury@example.com", "applicant phone": "+961 3 555 214",
        "applicant occupation": "Civil engineer", "applicant employer": "Granite Construction Co.",
        "purpose of visit": "Family visit", "intended arrival date": "2027-04-02",
        "intended departure date": "2027-04-30", "address during the stay": "14 Elm Court, Mississauga, ON L5B 1M2",
        "countries visited in the last five years": ["Italy", "Japan", "Mexico"],
        "applicant previously refused a visa": False, "applicant has a criminal record": False,
        "companion 1 surname": "Khoury", "companion 1 given names": "Nour", "companion 1 date of birth": "1993-02-14",
        "companion 1 relationship to applicant": "Spouse", "companion 1 passport number": "LR5510382",
        "companion 2 surname": "Khoury", "companion 2 given names": "Lea", "companion 2 date of birth": "2019-09-30",
        "companion 2 relationship to applicant": "Child", "companion 2 passport number": "LR7719046",
        "sponsor full name": "Maya Khoury-Abara", "sponsor phone": "+1 905 555 0162",
        "sponsor address": "14 Elm Court, Mississauga, ON L5B 1M2",
        "emergency contact full name": "Elias Khoury", "emergency contact phone": "+961 1 555 780",
        # Decoys
        "applicant previous passport number": "LR1029384", "applicant former nationality": "Canada",
        "applicant previous employer": "Polar Logistics",
    }
    expected = {
        "a_surname": "Khoury", "a_given": "Rami Elias", "a_dob": "1991-06-23", "a_nat": "Lebanon",
        "a_passport": "LR4482917", "a_issued": "2022-03-10", "a_expiry": "2032-03-09",
        "a_email": "rami.khoury@example.com", "a_phone": "+961 3 555 214", "a_job": "Civil engineer",
        "a_employer": "Granite Construction Co.", "a_purpose": "Family visit", "a_arrive": "2027-04-02",
        "a_depart": "2027-04-30", "a_address": "14 Elm Court, Mississauga, ON L5B 1M2",
        "a_visited": ["Italy", "Japan", "Mexico"], "a_refused": False, "a_record": False,
        "c1_surname": "Khoury", "c1_given": "Nour", "c1_dob": "1993-02-14", "c1_rel": "Spouse", "c1_passport": "LR5510382",
        "c2_surname": "Khoury", "c2_given": "Lea", "c2_dob": "2019-09-30", "c2_rel": "Child", "c2_passport": "LR7719046",
        "c3_surname": "", "c3_given": "", "c3_dob": "", "c3_rel": "", "c3_passport": "",
        "s_name": "Maya Khoury-Abara", "s_phone": "+1 905 555 0162", "s_address": "14 Elm Court, Mississauga, ON L5B 1M2",
        "e_name": "Elias Khoury", "e_phone": "+961 1 555 780",
    }
    return "Visa application", sections, facts, expected


def build_conference_registration():
    sections = [
        fieldset("Attendee",
                 control("text", "name", "Full name"), control("email", "email", "Email"),
                 control("text", "org", "Organization"), control("text", "title", "Job title"),
                 dropdown("country", "Country", COUNTRIES), control("url", "profile", "Profile URL"),
                 dropdown("ticket", "Ticket type", ["Student", "Standard", "Premium", "Speaker"]),
                 dropdown("size", "T-shirt size", ["XS", "S", "M", "L", "XL", "XXL"]),
                 dropdown("diet", "Dietary requirements",
                          ["Vegetarian", "Vegan", "Gluten-free", "Halal", "Kosher", "Nut allergy"], multiple=True),
                 aria_multilistbox("sessions", "Sessions to attend",
                                   ["Opening keynote", "Workshop A: Testing", "Workshop B: Security", "Closing panel"]),
                 control("textarea", "access", "Accessibility needs")),
        fieldset("Travel",
                 control("date", "arrive", "Arrival date"), control("date", "depart", "Departure date"),
                 control("checkbox", "hotel", "I need hotel accommodation"),
                 control("number", "guests", "Number of accompanying guests", ' min="0"')),
        fieldset("Emergency contact", control("text", "e_name", "Full name"), control("tel", "e_phone", "Phone")),
        fieldset("Invoice",
                 control("text", "inv_company", "Company name"), control("text", "inv_vat", "VAT number"),
                 control("text", "inv_address", "Billing address"), control("text", "promo", "Promo code")),
    ]
    facts = {
        "attendee full name": "Sofia Bergstrom", "attendee email": "sofia.b@example.se",
        "attendee organization": "Lumen Studios", "attendee job title": "Lead Engineer", "attendee country": "Sweden",
        "attendee profile URL": "https://sofia.example.se", "ticket type": "Standard", "t-shirt size": "XL",
        "dietary requirements": ["Vegetarian", "Nut allergy"],
        "sessions to attend": ["Workshop B: Security", "Closing panel"],
        "accessibility needs": "Step-free access to the stage, please.",
        "arrival date": "2027-05-11", "departure date": "2027-05-14", "needs hotel accommodation": True,
        "number of accompanying guests": 1,
        "emergency contact full name": "Erik Bergstrom", "emergency contact phone": "+46 70 555 0133",
        "invoice company name": "Lumen Studios AB", "invoice VAT number": "SE556677889901",
        "invoice billing address": "Vasagatan 10, 111 20 Stockholm",
        # Decoys and extras
        "attendee former organization": "Kestrel Aviation", "accompanying guest full name": "Linnea Bergstrom",
        "attendee t-shirt size last year": "L", "attendee favorite session last year": "Opening keynote",
    }
    expected = {
        "name": "Sofia Bergstrom", "email": "sofia.b@example.se", "org": "Lumen Studios", "title": "Lead Engineer",
        "country": "Sweden", "profile": "https://sofia.example.se", "ticket": "Standard", "size": "XL",
        "diet": ["Vegetarian", "Nut allergy"], "sessions": ["Workshop B: Security", "Closing panel"],
        "access": "Step-free access to the stage, please.", "arrive": "2027-05-11", "depart": "2027-05-14",
        "hotel": True, "guests": "1", "e_name": "Erik Bergstrom", "e_phone": "+46 70 555 0133",
        "inv_company": "Lumen Studios AB", "inv_vat": "SE556677889901",
        "inv_address": "Vasagatan 10, 111 20 Stockholm", "promo": "",
    }
    return "Conference registration", sections, facts, expected


FORMS = {
    "job_application": build_job_application,
    "medical_intake": build_medical_intake,
    "checkout": build_checkout,
    "visa_application": build_visa_application,
    "conference_registration": build_conference_registration,
}


def main():
    for folder, build in FORMS.items():
        title, sections, facts, expected = build()
        html = (f'<!doctype html>\n<html lang="en"><meta charset="utf-8"><title>{title} | benchmark fixture</title>\n'
                f"{STYLE}\n<h1>{title}</h1><p>Synthetic benchmark fixture. Not a real form.</p>\n"
                f'<form id="{folder}">\n' + "\n".join(sections) + "\n</form>\n" + SCRIPT + "</html>\n")
        target = DIRECTORY / folder
        target.mkdir(exist_ok=True)
        (target / "form.html").write_text(html, encoding="utf-8")
        (target / "facts.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (target / "expected.json").write_text(json.dumps(expected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        candidates = sum(len(v) if isinstance(v, list) else 1 for v in facts.values())
        print(f"{folder:26} {len(expected):3} fields, {candidates:3} candidate facts")


if __name__ == "__main__":
    main()
