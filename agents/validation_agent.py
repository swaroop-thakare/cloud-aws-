import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError


class DocumentFields(BaseModel):
	name: str = Field(default="")
	dob: str = Field(default="")  # YYYY-MM-DD preferred
	id_number: str = Field(default="")
	address: str = Field(default="")
	email: Optional[str] = Field(default=None)
	phone: Optional[str] = Field(default=None)
	nationality: Optional[str] = Field(default=None)


class ValidationResult(BaseModel):
	is_valid: bool
	issues: List[str]


DATE_FORMATS = [
	"%Y-%m-%d",
	"%d-%m-%Y",
	"%d/%m/%Y",
	"%m/%d/%Y",
]

ID_REGEX = re.compile(r"^[A-Za-z0-9\-]{5,}$")


def _validate_date(dob: str, issues: List[str]) -> None:
	if not dob:
		issues.append("dob is missing")
		return
	for fmt in DATE_FORMATS:
		try:
			_ = datetime.strptime(dob, fmt)
			return
		except Exception:
			continue
	issues.append("dob has invalid format; expected YYYY-MM-DD or common variants")


def _validate_id_number(id_number: str, issues: List[str]) -> None:
	if not id_number:
		issues.append("id_number is missing")
		return
	if not ID_REGEX.match(id_number):
		issues.append("id_number format invalid; expected alphanumeric with optional hyphen, length>=5")


def _validate_non_empty(field_name: str, value: Optional[str], issues: List[str]) -> None:
	if value is None or str(value).strip() == "":
		issues.append(f"{field_name} is missing")


def validate_document_fields(data: Dict) -> Tuple[DocumentFields, ValidationResult]:
	"""Validate structured JSON and return parsed model plus validation result."""
	issues: List[str] = []

	try:
		parsed = DocumentFields(**data)
	except ValidationError as e:
		issues.append(f"schema validation error: {e}")
		# Proceed with partial data
		parsed = DocumentFields(**{k: data.get(k, "") for k in DocumentFields.model_fields.keys()})

	_validate_non_empty("name", parsed.name, issues)
	_validate_date(parsed.dob, issues)
	_validate_id_number(parsed.id_number, issues)
	_validate_non_empty("address", parsed.address, issues)

	is_valid = len(issues) == 0
	return parsed, ValidationResult(is_valid=is_valid, issues=issues)
