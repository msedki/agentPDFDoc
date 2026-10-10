from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class RuntimeMode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["interactive", "ingestion"]


class DocumentMove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relative_path: str = Field(min_length=1, max_length=1024)


class SelectedSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extractionRevisionId: str = Field(min_length=1, max_length=128)
    blockId: str = Field(min_length=1, max_length=256)
    blockTextSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    offsetUnit: Literal["unicode_code_point"]
    startOffset: StrictInt = Field(ge=0)
    endOffset: StrictInt = Field(ge=1)

    @model_validator(mode="after")
    def offsets(self):
        if self.startOffset >= self.endOffset:
            raise ValueError("Offsets de sélection invalides.")
        return self


class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["library", "folder", "documents", "section", "pages", "selection", "sheet", "cell_range"]
    folderId: str | None = None
    recursive: Literal[True] = True
    documentIds: list[str] = Field(default_factory=list, max_length=1000)
    versionId: str | None = None
    sectionId: str | None = None
    pageStart: StrictInt | None = Field(default=None, ge=0)
    pageEnd: StrictInt | None = Field(default=None, ge=0)
    spans: list[SelectedSpan] = Field(default_factory=list, max_length=128)
    extractionRevisionId: str | None = Field(default=None, min_length=1, max_length=128)
    sheetId: str | None = Field(default=None, min_length=1, max_length=256)
    rowStart: StrictInt | None = Field(default=None, ge=1, le=1048576)
    rowEnd: StrictInt | None = Field(default=None, ge=1, le=1048576)
    columnStart: StrictInt | None = Field(default=None, ge=1, le=16384)
    columnEnd: StrictInt | None = Field(default=None, ge=1, le=16384)

    @model_validator(mode="after")
    def required_values(self):
        if self.kind == "folder" and not self.folderId:
            raise ValueError("Un dossier est requis.")
        if self.kind == "documents" and not self.documentIds:
            raise ValueError("Au moins un document est requis.")
        if self.kind in {"pages", "section", "selection", "sheet", "cell_range"} and not self.versionId:
            raise ValueError("Une version est requise.")
        if self.kind == "section" and not self.sectionId:
            raise ValueError("Une section est requise.")
        if self.kind == "selection" and not self.spans:
            raise ValueError("Une sélection est requise.")
        if self.kind == "pages" and (self.pageStart is None or self.pageEnd is None or self.pageStart > self.pageEnd):
            raise ValueError("Une plage de pages valide est requise.")
        if self.kind in {"sheet", "cell_range"}:
            if not self.extractionRevisionId or not self.sheetId:
                raise ValueError("Une feuille et sa révision d'extraction sont requises.")
            if self.kind == "cell_range" and (self.rowStart is None or self.rowEnd is None
                    or self.columnStart is None or self.columnEnd is None
                    or self.rowStart > self.rowEnd or self.columnStart > self.columnEnd):
                raise ValueError("Une plage de cellules ordonnée est requise.")
        return self


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=12000)
    scope: Scope
    mode: Literal["question", "selection", "section", "comparison", "compare", "factual", "ordinary", "analysis"] = "question"
    conversation_id: str | None = None
    followup_of: str | None = None
    focus: dict | None = None

    @model_validator(mode="after")
    def question_and_comparison(self):
        self.question = self.question.strip()
        if not self.question:
            raise ValueError("La question est vide.")
        if self.mode == "compare":
            self.mode = "comparison"
        if self.mode == "comparison" and (self.scope.kind != "documents" or not 2 <= len(set(self.scope.documentIds)) <= 4):
            raise ValueError("Une comparaison exige deux à quatre documents.")
        if self.focus is not None:
            allowed = {"query_id", "source_id", "version_id", "block_id", "identifier"}
            if set(self.focus) - allowed or not all(isinstance(value, str) and 0 < len(value) <= 256 for value in self.focus.values()):
                raise ValueError("Focus invalide.")
        return self


class EvaluationContextRequest(QueryRequest):
    prior_user_question: str | None = Field(default=None, min_length=1, max_length=12000)
