import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from quiz.models import Question


class Command(BaseCommand):
    help = 'Import PSE MCQ practice questions from a DOCX file into the Question table.'

    def add_arguments(self, parser):
        parser.add_argument('docx_path', nargs='?', default=r'C:\Users\sahan\Downloads\PSE_MCQ_Practice.docx')

    def handle(self, *args, **options):
        docx_path = Path(options['docx_path'])
        if not docx_path.exists():
            raise CommandError(f'DOCX file not found: {docx_path}')

        questions = self._parse_docx(docx_path)
        created = 0
        updated = 0

        for item in questions:
            _, is_created = Question.objects.update_or_create(
                category=item['category'],
                text=item['text'],
                defaults={
                    'option_a': item['option_a'],
                    'option_b': item['option_b'],
                    'option_c': item['option_c'],
                    'option_d': item['option_d'],
                    'correct_option': item['correct_option'],
                },
            )
            if is_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Imported {len(questions)} questions from {docx_path}. Created: {created}, updated: {updated}.'
        ))

    def _parse_docx(self, docx_path):
        with zipfile.ZipFile(docx_path) as archive:
            xml = archive.read('word/document.xml')

        namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        root = ET.fromstring(xml)
        paragraphs = [
            ''.join(node.text or '' for node in para.findall('.//w:t', namespace)).strip()
            for para in root.findall('.//w:p', namespace)
        ]

        questions = []
        current_category = 'General'
        current_question = None

        category_pattern = re.compile(r'^\d+\.\s+(.*)$')
        question_pattern = re.compile(r'^Q\d+\.\s+(.*)$')
        option_pattern = re.compile(r'^([A-D])\)\s+(.*)$')
        answer_pattern = re.compile(r'^Answer:\s*([A-D])\)\s*(.*)$')

        for line in paragraphs:
            if not line:
                continue

            category_match = category_pattern.match(line)
            if category_match and not line.startswith('Q'):
                current_category = category_match.group(1).strip()
                continue

            question_match = question_pattern.match(line)
            if question_match:
                if current_question is not None:
                    questions.append(current_question)
                current_question = {
                    'category': current_category,
                    'text': question_match.group(1).strip(),
                    'option_a': '',
                    'option_b': '',
                    'option_c': '',
                    'option_d': '',
                    'correct_option': '',
                }
                continue

            option_match = option_pattern.match(line)
            if option_match and current_question is not None:
                option_key = option_match.group(1).lower()
                current_question[f'option_{option_key}'] = option_match.group(2).strip()
                continue

            answer_match = answer_pattern.match(line)
            if answer_match and current_question is not None:
                current_question['correct_option'] = answer_match.group(1)
                continue

        if current_question is not None:
            questions.append(current_question)

        self._validate_questions(questions)
        return questions

    def _validate_questions(self, questions):
        if not questions:
            raise CommandError('No questions were parsed from the DOCX file.')

        for index, question in enumerate(questions, start=1):
            missing = [field for field in ('option_a', 'option_b', 'option_c', 'option_d', 'correct_option') if not question[field]]
            if missing:
                raise CommandError(f'Question {index} is incomplete: missing {", ".join(missing)}.')