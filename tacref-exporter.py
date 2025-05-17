import xml.etree.ElementTree as ET
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Image
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.units import inch
import os
from PIL import Image as PILImage
import io
import tkinter as tk
from tkinter import filedialog
from pathlib import Path


def select_bms_directory():
    """
    Show a directory selection dialog and validate that it's a Falcon BMS directory
    Returns the selected directory path or None if invalid/cancelled
    """
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    directory = filedialog.askdirectory(
        title="Select Falcon BMS Main Directory",
        mustexist=True
    )

    if not directory:
        return None

    # Verify this is a BMS directory by checking for required paths
    bms_path = Path(directory)
    tacref_path = bms_path / "Data" / "TerrData" / "TacRefDB.xml"
    art_path = bms_path / "Data" / "Art" / "TacRData"

    if not tacref_path.exists():
        tk.messagebox.showerror(
            "Error",
            "Selected directory does not appear to be a valid Falcon BMS directory.\n"
            "Could not find TacRefDB.xml in Data/TerrData/"
        )
        return None

    if not art_path.exists():
        tk.messagebox.showerror(
            "Error",
            "Selected directory does not appear to be a valid Falcon BMS directory.\n"
            "Could not find Art/TacRData directory"
        )
        return None

    return str(bms_path)


class TacticalReferenceDocument(SimpleDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self.toc = TableOfContents()

    def afterFlowable(self, flowable):
        """Registers TOC entries."""
        if flowable.__class__.__name__ == 'Paragraph':
            text = flowable.getPlainText()
            style = flowable.style.name
            if style == 'Heading1':
                self.notify('TOCEntry', (0, text, self.page))
            # elif style == 'Heading2':
            #     self.notify('TOCEntry', (1, text, self.page))


def create_styles():
    """Create and return custom styles for the document"""
    styles = getSampleStyleSheet()

    # Title style
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        spaceAfter=30,
        keepWithNext=True
    ))

    # TOC styles
    styles.add(ParagraphStyle(
        name='TOCHeading',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        name='TOCEntry1',
        parent=styles['Normal'],
        fontSize=12,
        leftIndent=20,
        firstLineIndent=-20,
        spaceBefore=3,
        leading=16
    ))

    styles.add(ParagraphStyle(
        name='TOCEntry2',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=40,
        firstLineIndent=-20,
        spaceBefore=3,
        leading=16
    ))



    return styles


def convert_tga_to_png(tga_path):
    """Convert TGA image to PNG format in memory"""
    try:
        with PILImage.open(tga_path) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img = img.convert('RGBA')
            else:
                img = img.convert('RGB')

            # Save to bytes buffer
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            return img_byte_arr
    except Exception as e:
        print(f"Error converting image {tga_path}: {str(e)}")
        return None


def process_image(image_path, max_width=6 * inch, max_height=4 * inch):
    """Process and resize image while maintaining aspect ratio"""
    try:
        # Check if image exists
        if not os.path.exists(image_path):
            print(f"Image not found: {image_path}")
            return None

        # Convert TGA to PNG if needed
        if image_path.lower().endswith('.tga'):
            img_data = convert_tga_to_png(image_path)
            if img_data is None:
                return None
        else:
            # For non-TGA images, just read the file
            with open(image_path, 'rb') as f:
                img_data = io.BytesIO(f.read())

        # Create PIL Image object
        with PILImage.open(img_data) as img:
            # Get original dimensions
            width, height = img.size

            # Calculate aspect ratio
            aspect = width / height

            # Determine new dimensions
            if width > max_width:
                width = max_width
                height = width / aspect

            if height > max_height:
                height = max_height
                width = height * aspect

        # Create ReportLab Image object
        img = Image(img_data, width=width, height=height)
        img.hAlign = 'CENTER'
        return img

    except Exception as e:
        print(f"Error processing image {image_path}: {str(e)}")
        return None


def create_pdf_from_tacref(bms_dir, output_pdf):
    # Construct paths
    xml_path = os.path.join(bms_dir, "Data", "TerrData", "TacRefDB.xml")
    art_path = os.path.join(bms_dir, "Data", "Art", "TacRData")

    # Parse XML file
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Create PDF document using custom template
    doc = TacticalReferenceDocument(output_pdf, pagesize=letter)
    styles = create_styles()

    # Create story (content) for the PDF
    story = []

    # Add title
    story.append(Paragraph("Tactical Reference Database", styles['CustomTitle']))

    # Add table of contents
    toc = TableOfContents()
    toc.levelStyles = [
        styles['TOCEntry1'],
        styles['TOCEntry2']
    ]
    story.append(Paragraph('Table of Contents', styles['TOCHeading']))
    story.append(toc)
    story.append(PageBreak())

    # Process each TacRefData entry
    for tacref in root.findall('TacRefData'):
        main_data = tacref.find('MainData')
        name = main_data.find('Name').text
        pic_name = main_data.find('PicName').text if main_data.find('PicName') is not None else None

        # Add weapon name as heading
        story.append(Paragraph(name, styles['Heading1']))

        # Add image if available
        if pic_name:
            image_path = os.path.join(art_path, f"{pic_name}.tga")
            if os.path.exists(image_path):
                img = process_image(image_path)
                if img is not None:
                    story.append(img)

        # Process categories
        for category in tacref.findall('CategoryData'):
            title = category.find('CategoryTitle').text
            description = category.find('CategoryDescription').text

            # Add category title
            if title:
                story.append(Paragraph(title, styles['Heading2']))

            # Add description
            if description:
                # Split description into lines and create paragraphs
                for line in description.strip().split('\n'):
                    if line.strip():
                        story.append(Paragraph(line.strip(), styles['Normal']))

        # Add description data if available
        desc_data = tacref.find('DescriptionData')
        if desc_data is not None and desc_data.text:
            story.append(Paragraph("Description", styles['Heading2']))
            story.append(Paragraph(desc_data.text.strip(), styles['Normal']))

        # Add page break after each entry
        story.append(PageBreak())

    # Build PDF with multiBuild for TOC support
    doc.multiBuild(story)


if __name__ == "__main__":
    bms_dir = select_bms_directory()

    if bms_dir:
        # Create output directory if it doesn't exist
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Create PDF
        output_pdf = os.path.join(output_dir, "tactical_reference.pdf")

        create_pdf_from_tacref(bms_dir, output_pdf)

        # Show success message
        tk.messagebox.showinfo(
            "Success",
            f"PDF has been created successfully!\nLocation: {output_pdf}"
        )
    else:
        print("Operation cancelled or invalid directory selected.")

    # create_pdf_from_tacref("TacRefDB.xml", "tactical_reference.pdf")