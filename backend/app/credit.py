"""Explainable credit-building roadmap for international students.

General educational guidance only. Rules and products differ by country and
lender, so every step tells the student to verify terms with the lender.
"""


def roadmap(country: str, months_in_country: int, has_local_id: bool, has_income: bool) -> dict:
    steps = []
    if not has_local_id:
        steps.append({"step": "Get the local ID number your banks and lenders ask for",
                      "why": "Most credit bureaus need a verifiable ID before they can create a file.",
                      "when": "First 2 weeks"})
    steps.append({"step": "Open a student or basic bank account and set up salary/allowance deposits",
                  "why": "A stable account history helps when you later apply for credit.",
                  "when": "Month 1"})
    steps.append({"step": "Ask lenders about a student, secured or low-limit starter card",
                  "why": "Starter products accept thin credit files. A secured card uses your deposit as the limit.",
                  "when": "Month 1-3" if months_in_country < 6 else "Now"})
    steps.append({"step": "Use it for one small recurring bill and pay the full balance on time",
                  "why": "On-time payment history is usually the biggest factor in a credit score.",
                  "when": "Every month"})
    steps.append({"step": "Keep usage below 30% of the limit",
                  "why": "High utilisation signals risk to lenders.",
                  "when": "Every month"})
    if has_income:
        steps.append({"step": "Ask whether rent or utility payments can be reported to the bureau",
                      "why": "Some services add on-time rent payments to your file.",
                      "when": "Month 3-6"})
    steps.append({"step": "Check your credit report once or twice a year",
                  "why": "Catches errors and identity fraud early.",
                  "when": "Every 6 months"})
    avoid = ["Do not apply for many cards at once; each application can lower your score.",
             "Do not pay a service that promises to 'fix' credit quickly.",
             "Never share card PINs or OTPs, even with someone claiming to be your bank."]
    horizon = "6-12 months to a first usable score" if months_in_country < 12 else "3-6 months to improve an existing thin file"
    return {"country": country, "months_in_country": months_in_country, "steps": steps,
            "avoid": avoid, "horizon": horizon,
            "disclaimer": "Educational guidance. Verify terms with the lender; products vary by country."}
