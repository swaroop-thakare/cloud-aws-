from typing import Dict

from .validation_agent import DocumentFields, ValidationResult


def generate_audit_report(data: DocumentFields, validation: ValidationResult) -> str:
	"""Produce a succinct, human-readable explanation of validation results."""
	if validation.is_valid:
		return (
			"Valid document. All required fields present and correctly formatted. "
			f"Name: {data.name or 'N/A'}, DOB: {data.dob or 'N/A'}, ID: {data.id_number or 'N/A'}."
		)

	lines = ["Document has issues:"]
	for issue in validation.issues:
		lines.append(f"- {issue}")
	return "\n".join(lines)
