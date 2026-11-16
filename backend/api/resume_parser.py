import io
import PyPDF2
import docx

def extract_resume_text(uploaded_file) -> str:
    filename = (uploaded_file.name or "").lower()
    
    if filename.endswith(".pdf"):
        reader = PyPDF2.PdfReader(uploaded_file)
        text_parts = []
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text_parts.append(extracted)
        return "\n".join(text_parts).strip()

    elif filename.endswith(".docx"):
        doc = docx.Document(uploaded_file)
        paragraphs = [p.text for p in doc.paragraphs if p.text]
        return "\n".join(paragraphs).strip()

    else:
        raise ValueError("Unsupported file format. Only PDF and DOCX allowed.")
