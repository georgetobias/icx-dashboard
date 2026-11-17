"""Generate fictional survey ratings without reading any external input."""
from pathlib import Path
import csv

FIELDS = ["Employee ID", "Email Address", "Group", "Group Rated", "Rating", "Frequency Category", "Criticality Score", "Criticality", "Band", "Role", "Tenure Category", "Age Range", "Division", "Division Rated", "Service", "Service Received", "Territory", "Territory Grouping"]
GROUPS = ["Demo Operations", "Demo Technology", "Demo Support"]

def generate(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    ratings = ["BUSTED", "LEVELED", "UPLIFTED", "EXCEPTIONAL"]
    frequencies = ["Daily", "Weekly", "Monthly", "Quarterly", "Annual", "Ad hoc / Upon request"]
    criticality_labels = ["Not Critical", "Somewhat Critical", "Critical", "Very Critical"]
    for person in range(18):
        customer = GROUPS[person % len(GROUPS)]
        for service in range(3):
            criticality = (person + service) % 4 + 1
            rows.append({
                "Employee ID": f"DEMO-{person:03d}",
                "Email Address": f"demo-{person:03d}@example.invalid",
                "Group": customer,
                "Group Rated": GROUPS[(person + service) % len(GROUPS)],
                "Rating": ratings[(person * 3 + service) % 4],
                "Frequency Category": frequencies[(person + service) % len(frequencies)],
                "Criticality Score": criticality,
                "Criticality": criticality_labels[criticality - 1],
                "Band": ["Demo Band A", "Demo Band B"][person % 2],
                "Role": ["Individual Contributor", "People Manager"][person % 2],
                "Tenure Category": ["Less than 3 years", "3 to 5 years"][person % 2],
                "Age Range": ["20 - 30 years old", "31 - 40 years old"][person % 2],
                "Division": f"Demo Customer Division {person % 2 + 1}",
                "Division Rated": f"Demo Provider Division serving Territory {service + 1}",
                "Service": f"Demo Service {service + 1}",
                "Service Received": f"Fictional service category {service + 1}",
                "Territory": f"Demo Territory {service + 1}",
                "Territory Grouping": f"Demo Territory Group {service + 1}",
            })
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    schema = destination.with_name("schema.csv")
    with schema.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerow(FIELDS)

if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1] / "data" / "demo.csv")
