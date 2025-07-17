import io
from pdfminer.high_level import extract_text

# PDF parsing function
def parse_pdf(file):
    # Read the file content into a bytes buffer
    file_stream = io.BytesIO(file.read())
    
    # pdfminer to extract text from the PDF file stream
    text = extract_text(file_stream)
    return text
