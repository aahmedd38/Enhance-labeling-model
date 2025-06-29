import os
import sys
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QTextEdit
)
from PyQt5.QtCore import Qt


def calculate_accuracy_all_labels(input_file, output_file):
    input_df = pd.read_excel(input_file)
    output_df = pd.read_excel(output_file)

    output_map = {
        str(row['code']).strip(): str(row.get('validated_label', '')).strip().lower()
        for _, row in output_df.iterrows()
        if pd.notna(row.get('code'))
    }

    label_stats = {}
    total = 0
    matched_total = 0

    for _, row in input_df.iterrows():
        code = str(row.get('code', '')).strip()
        label = str(row.get('label', '')).strip().lower()

        if not code:
            continue

        validated_label = output_map.get(code)
        label_stats.setdefault(label, {"matched": 0, "total": 0})
        label_stats[label]["total"] += 1
        total += 1

        if validated_label == label:
            label_stats[label]["matched"] += 1
            matched_total += 1

    overall_accuracy = (matched_total / total) * 100 if total > 0 else 0
    return overall_accuracy, matched_total, total, label_stats


class AccuracyCheckerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Accuracy Checker")
        self.setMinimumWidth(500)
        self.layout = QVBoxLayout()

        self.input_label = QLabel("Input File: Not selected")
        self.output_label = QLabel("Output File: Not selected")
        self.result_label = QLabel("Accuracy: N/A")
        self.detail_box = QTextEdit()
        self.detail_box.setReadOnly(True)
        self.detail_box.setMinimumHeight(150)

        self.select_input_btn = QPushButton("Select Input File")
        self.select_output_btn = QPushButton("Select Output File")
        self.check_accuracy_btn = QPushButton("Check Accuracy")

        self.select_input_btn.clicked.connect(self.select_input_file)
        self.select_output_btn.clicked.connect(self.select_output_file)
        self.check_accuracy_btn.clicked.connect(self.run_accuracy_check)

        self.layout.addWidget(self.input_label)
        self.layout.addWidget(self.select_input_btn)
        self.layout.addWidget(self.output_label)
        self.layout.addWidget(self.select_output_btn)
        self.layout.addWidget(self.check_accuracy_btn)
        self.layout.addWidget(self.result_label)
        self.layout.addWidget(QLabel("Per-label accuracy:"))
        self.layout.addWidget(self.detail_box)

        self.setLayout(self.layout)
        self.input_file = None
        self.output_file = None

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Input Excel File", "", "Excel Files (*.xlsx *.xls)")
        if file_path:
            self.input_file = file_path
            self.input_label.setText(f"Input File: {os.path.basename(file_path)}")

    def select_output_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Output Excel File", "", "Excel Files (*.xlsx *.xls)")
        if file_path:
            self.output_file = file_path
            self.output_label.setText(f"Output File: {os.path.basename(file_path)}")

    def run_accuracy_check(self):
        if not self.input_file or not self.output_file:
            QMessageBox.warning(self, "Missing File", "Please select both input and output files.")
            return

        try:
            accuracy, matched, total, label_stats = calculate_accuracy_all_labels(self.input_file, self.output_file)
            self.result_label.setText(f"Overall Accuracy: {accuracy:.2f}% ({matched}/{total})")

            details = ""
            for label, stats in label_stats.items():
                acc = (stats["matched"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                details += f"{label}: {acc:.2f}% ({stats['matched']}/{stats['total']})\n"

            self.detail_box.setPlainText(details.strip())

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to calculate accuracy:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AccuracyCheckerApp()
    window.show()
    sys.exit(app.exec_())
