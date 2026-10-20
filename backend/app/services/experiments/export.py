"""Experiment export: JSON (summary) + PDF (fpdf2)."""


def _latin(s: str) -> str:
    return str(s).replace("₹", "Rs.").replace("—", "-").replace("→", "->").encode("latin-1", "replace").decode("latin-1")


def to_pdf(exp: dict, summary: dict) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "AI QueryHub - Investigation Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for line in (f"Experiment: {exp['id']}", f"Question: {exp['question']}", f"Status: {summary.get('status')}",
                 f"Spec: {summary.get('spec')}", f"Stop reason: {summary.get('stop_reason')}  |  "
                 f"Explained: {summary.get('explained')}  |  Residual: {summary.get('residual_share')}"):
        pdf.multi_cell(0, 5, _latin(line), new_x="LMARGIN", new_y="NEXT")

    def section(title: str) -> None:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)

    section("Narrative (claims)")
    for c in summary.get("claims", []):
        pdf.multi_cell(0, 5, _latin(f"[{c['claim_type']}] {c['sentence']}"), new_x="LMARGIN", new_y="NEXT")
    gate = (summary.get("verify") or {}).get("gate") or {}
    section("Verify")
    pdf.multi_cell(0, 5, _latin(f"Gate: method={gate.get('method')} z={gate.get('z')} status={gate.get('status')}"),
                   new_x="LMARGIN", new_y="NEXT")
    section("Findings")
    for f in summary.get("findings", []):
        pdf.multi_cell(0, 5, _latin(f"{f['key']}: {f['status']} | share={f['share_of_delta']:.3f} | "
                                    f"score={f.get('score')} {f.get('label') or ''} | q={f.get('q_value')} | "
                                    f"{f['statement']}"), new_x="LMARGIN", new_y="NEXT")
    section("Queries (provenance)")
    for q in summary.get("queries", []):
        pdf.multi_cell(0, 4, _latin(f"{q['id']} {q['purpose']} rows={q['row_count']} sha256={q['checksum'][:16]}..."),
                       new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
