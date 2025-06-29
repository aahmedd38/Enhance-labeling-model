import os
import sys
import pandas as pd
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QPlainTextEdit
)
from PyQt5.QtCore import Qt
MAX_CODE_TOKEN_LENGTH = 14000 #

class ReviewGUI(QWidget):
    """GUI for human-in-the-loop vulnerability review"""
    
    def __init__(self, hitl_data):
        super().__init__()
        self.setWindowTitle("HITL Vulnerability Review")
        self.hitl_data = hitl_data
        self.approved = []
        self.index = 0
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        self.layout = QVBoxLayout()

        # Case counter label
        self.case_label = QLabel()
        self.case_label.setAlignment(Qt.AlignCenter)
        self.case_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 6px;")

        # Code display area
        self.code_display = QPlainTextEdit()
        self.code_display.setReadOnly(True)
        self.code_display.setStyleSheet("""
            background-color: #f5f5f5; 
            font-family: monospace; 
            font-size: 12px;
        """)

        # Input fields
        self.vuln_edit = QTextEdit()
        self.vuln_edit.setPlaceholderText("Vulnerable / Non-Vulnerable")
        self.vuln_edit.setFixedHeight(30)

        self.type_edit = QTextEdit()
        self.type_edit.setPlaceholderText("Vulnerability Type")
        self.type_edit.setFixedHeight(30)

        self.severity_edit = QTextEdit()
        self.severity_edit.setPlaceholderText("Severity")
        self.severity_edit.setFixedHeight(30)

        # Action buttons
        self.btn_approve = QPushButton("✅ Approve")
        self.btn_reject = QPushButton("❌ Reject")
        self.btn_approve.clicked.connect(self.approve)
        self.btn_reject.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_approve)
        btn_layout.addWidget(self.btn_reject)
        btn_layout.addStretch()

        # Assemble layout
        self.layout.addWidget(self.case_label)
        self.layout.addWidget(self.code_display)
        self.layout.addWidget(QLabel("Vulnerability:"))
        self.layout.addWidget(self.vuln_edit)
        self.layout.addWidget(QLabel("Type:"))
        self.layout.addWidget(self.type_edit)
        self.layout.addWidget(QLabel("Severity:"))
        self.layout.addWidget(self.severity_edit)
        self.layout.addLayout(btn_layout)

        self.setLayout(self.layout)
        self.display_case()

    def display_case(self):
        """Display the current case"""
        if self.index >= len(self.hitl_data):
            self.close()
            return

        case = self.hitl_data[self.index]
        self.case_label.setText(f"Case {self.index + 1} / {len(self.hitl_data)}")
        self.code_display.setPlainText(case['code'])
        self.vuln_edit.setText(case.get('validated_label', ''))
        self.type_edit.setText(case.get('validated_type', ''))
        self.severity_edit.setText(case.get('validated_severity', ''))

    def approve(self):
        """Approve the current case with edits"""
        edited_case = self.hitl_data[self.index].copy()
        edited_case.update({
            'validated_label': self.vuln_edit.toPlainText().strip(),
            'validated_type': self.type_edit.toPlainText().strip(),
            'validated_severity': self.severity_edit.toPlainText().strip(),
            'needs_review': False
        })
        self.approved.append(edited_case)
        self.index += 1
        self.display_case()

    def reject(self):
        """Reject the current case"""
        self.index += 1
        self.display_case()

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key_Right:
            self.approve()
        elif event.key() == Qt.Key_Left:
            self.reject()


def review_hitl_with_pyqt(hitl_data):
    """Launch the HITL review GUI"""
    app = QApplication(sys.argv)
    window = ReviewGUI(hitl_data)
    window.resize(700, 600)
    window.show()
    app.exec_()
    return window.approved


def load_dataset(file_path):
    """Load dataset from CSV file"""
    return pd.read_csv(file_path).to_dict('records')


def clean_data(dataset, code_column):
    """Clean and deduplicate dataset"""
    cleaned = [
        item for item in dataset
        if item.get(code_column) and isinstance(item[code_column], str) and item[code_column].strip()
    ]
    return list({item[code_column]: item for item in cleaned}.values())


def label_code(llm, code):
    """Label code snippet with vulnerability information using LLM"""
    if len(code) > MAX_CODE_TOKEN_LENGTH:
        code = code[:MAX_CODE_TOKEN_LENGTH] + "\n... [Code truncated for analysis due to length] ..."
    prompt = f"""You are a highly skilled and precise security analyst. Your task is to analyze the provided code snippet for security vulnerabilities and classify it rigorously.

INSTRUCTIONS:
1.  **Analyze ALL aspects of the code** to identify any potential security flaws, regardless of existing comments or labels.
2.  **Focus strictly on actual security vulnerabilities**, not coding style, performance, or general bug fixes.
3.  **Be extremely specific with vulnerability types.** Examples: "SQL Injection", "Cross-Site Scripting (XSS)", "Path Traversal", "Insecure Deserialization", "Command Injection", "Buffer Overflow", "Broken Authentication", "Information Disclosure", "Insecure Cryptography", "Missing Authorization". If truly non-vulnerable, use "None".
4.  **Use "Non-Vulnerable" ONLY if the code is demonstrably and unequivocally secure.** Avoid ambiguity.
5.  **Strictly adhere to the REQUIRED FORMAT** below. Any deviation will invalidate the response.

REQUIRED FORMAT (Exact casing and structure):
Vulnerability: Vulnerable or Non-Vulnerable
Type: [Specific vulnerability type, or "None"]
Severity: [Critical / High / Medium / Low / None]

SEVERITY ASSESSMENT GUIDELINES (Based on CVSS v3.1 principles):
* **Critical (9.0-10.0 CVSS Equivalent):** Allows for complete system compromise, unauthorized data exfiltration of sensitive information, full control takeover, or denial of service that significantly impacts business operations. Typically network-exploitable with low attack complexity, requiring no user interaction.
* **High (7.0-8.9 CVSS Equivalent):** Leads to significant data exposure (e.g., partial database dump), elevated privileges, or substantial impact on system availability or integrity. May require moderate attack complexity or limited user interaction.
* **Medium (4.0-6.9 CVSS Equivalent):** Results in limited information disclosure (e.g., error messages revealing internal paths), minor privilege escalation, or partial impact on system functions. Often requires higher attack complexity, specific conditions, or some user interaction.
* **Low (0.1-3.9 CVSS Equivalent):** Causes minimal information leakage, minor security weaknesses that are difficult to exploit, or requires local access/high attack complexity. Usually has limited impact on confidentiality, integrity, or availability.
* **None (0.0 CVSS Equivalent):** The code is secure, or the identified issue is not a security vulnerability.

CODE TO ANALYZE:
{code}"""

    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content.strip()

    label_data = {
        "vulnerability": "Unknown", 
        "type": "Unknown", 
        "severity": "Unknown"
    }
    
    for line in content.splitlines():
        if line.lower().startswith("vulnerability:"):
            label_data["vulnerability"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("type:"):
            label_data["type"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("severity:"):
            label_data["severity"] = line.split(":", 1)[1].strip()
            
    return label_data


def validate_label(llm, code, label_data):
    """Validate and correct vulnerability labels using LLM"""
    if len(code) > MAX_CODE_TOKEN_LENGTH:
            code = code[:MAX_CODE_TOKEN_LENGTH] + "\n... [Code truncated for validation due to length] ..."
    prompt = f"""You are a meticulous security auditor. Your task is to critically review and, if necessary, correct the provided vulnerability assessment. Your goal is to ensure absolute accuracy and consistency.

CURRENT ASSESSMENT:
Vulnerability: {label_data['vulnerability']}
Type: {label_data['type']}
Severity: {label_data['severity']}

VALIDATION RULES:
1.  **Strict Accuracy Check:** Is the overall vulnerability classification (Vulnerable/Non-Vulnerable) precisely correct for the given code?
2.  **Consistency for Non-Vulnerable:** If "Vulnerability: Non-Vulnerable", then "Type" MUST be "None" and "Severity" MUST be "None". Correct if inconsistent.
3.  **Specificity for Vulnerable:** If "Vulnerability: Vulnerable", then "Type" MUST be a specific vulnerability type (e.g., "SQL Injection", "XSS") and NOT "None", "Unknown", "Other", or "General". "Severity" MUST also be a valid level (Critical, High, Medium, Low) and NOT "None". Correct if inconsistent.
4.  **Severity Appropriateness:** For "Vulnerable" cases, does the assigned "Severity" accurately reflect the potential impact and exploitability based on CVSS principles (as previously defined: Critical > High > Medium > Low)? Adjust if mismatched.
5.  **If the current assessment is PERFECTLY correct and consistent with all rules, repeat the exact same values.** Do not introduce changes unless an error exists.

REQUIRED FORMAT (Exact casing and structure, NO additional text, NO explanations):
Vulnerability: [Vulnerable / Non-Vulnerable]
Type: [Specific vulnerability type, or "None"]
Severity: [Critical / High / Medium / Low / None]

CODE TO VALIDATE:
{code}"""

    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content.strip()

    validated = {
        "validated_label": label_data['vulnerability'],
        "validated_type": label_data['type'],
        "validated_severity": label_data['severity']
    }

    for line in content.splitlines():
        if line.lower().startswith("vulnerability:"):
            validated["validated_label"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("type:"):
            validated["validated_type"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("severity:"):
            validated["validated_severity"] = line.split(":", 1)[1].strip()
            
    return validated


def preprocessing(file_path, code_column="code"):
    """Main preprocessing pipeline with interruption and auto-save handling"""
    api_key = os.getenv("API KEY")
    llm = ChatOpenAI(model_name="gpt-3.5-turbo", api_key=api_key)

    dataset = load_dataset(file_path)
    print(f"Loaded {len(dataset)} rows from input file.")
    cleaned_data = clean_data(dataset, code_column)
    print(f"Retained {len(cleaned_data)} rows after cleaning.")

    output_data = []
    hitl_rows = []
    interrupted = False

    input_path = Path(file_path)
    autosave_path = input_path.with_name("autosave_" + input_path.name)

    try:
        for i, item in enumerate(cleaned_data):
            code = item[code_column]
            print(f" Processing snippet {i+1}/{len(cleaned_data)}...")

            label = label_code(llm, code)
            validated = validate_label(llm, code, label)

            needs_review = (
                "Unknown" in [validated["validated_type"], validated["validated_label"], validated["validated_severity"]] or
                validated["validated_type"].lower() in ["unknown", "other", "general"] or
                (validated["validated_label"] == "Vulnerable" and validated["validated_severity"] == "Low")
            )

            item_output = {
                "code": code,
                "validated_type": validated["validated_type"],
                "validated_label": validated["validated_label"],
                "validated_severity": validated["validated_severity"],
                "needs_review": needs_review
            }

            output_data.append(item_output)
            if needs_review:
                hitl_rows.append(item_output)

    except KeyboardInterrupt:
        print("\n\n⚠️ Process interrupted by user (Ctrl+C).")
        interrupted = True

    except Exception as e:
        print(f"\n❌ Unexpected error occurred: {e}")
        interrupted = True

    finally:
        if output_data:
            # Always save autosave file
            pd.DataFrame(output_data).to_csv(autosave_path, index=False)
            print(f"\n💾 Autosaved intermediate results to: {autosave_path} ({len(output_data)} rows)")

            if interrupted:
                print("⚠️ You can resume processing or manually inspect autosave file later.")
                return output_data

            # Normal end — prompt to continue
            choice = input("Do you want to save the processed data and resolve HITL? (y/n): ").strip().lower()
            if choice == "y":
                final_rows = [row for row in output_data if not row["needs_review"]]

                if hitl_rows:
                    print(f"\nLaunching HITL GUI for {len(hitl_rows)} uncertain cases...")
                    approved_hitl = review_hitl_with_pyqt(hitl_rows)
                    final_rows.extend(approved_hitl)

                output_path = input_path.with_name("final_output_" + input_path.name)
                pd.DataFrame(final_rows).to_csv(output_path, index=False)

                print(f"\n✅ Final dataset saved to: {output_path} ({len(final_rows)} rows)\n")
                return final_rows
            else:
                print("❌ Discarded all processed results.")
                return []
        else:
            print("⚠️ No data processed, nothing to save.")
            return []





def calculate_accuracy(input_file, output_file):
    """Calculate accuracy between input labels and validated output"""
    input_df = pd.read_csv(input_file)
    output_df = pd.read_csv(output_file)

    matched = 0
    total = 0

    # Create mapping of code to validated label
    output_map = {
        str(row['code']).strip(): str(row.get('validated_label', '')).strip().lower()
        for _, row in output_df.iterrows()
        if pd.notna(row.get('code'))
    }

    # Compare with original labels
    for _, row in input_df.iterrows():
        code = str(row.get('code', '')).strip()
        label = str(row.get('label', '')).strip().lower()
        if not code:
            continue
            
        total += 1
        validated_label = output_map.get(code)
        if validated_label == label:
            matched += 1

    accuracy = (matched / total) * 100 if total > 0 else 0
    print(f"\nAccuracy: {accuracy:.2f}% ({matched}/{total})")


if __name__ == "__main__":
    final = preprocessing("Vulnerable_dataset.csv")
    