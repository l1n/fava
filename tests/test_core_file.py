import datetime
from textwrap import dedent
import re

from beancount.core import data, amount
from beancount.core.number import D
import pytest

from fava.core.helpers import FavaAPIException
from fava.core.file import (next_key, leading_space, insert_metadata_in_file,
                            insert_entry, get_entry_slice, save_entry_slice)
from fava.core.fava_options import InsertEntryOption


def test_get_entry_slice(example_ledger):
    entry = example_ledger.get_entry('d4a067d229bfda57c8c984d1615da699')
    assert get_entry_slice(entry) == (
        """2016-05-03 * "Chichipotle" "Eating out with Joe"
  Liabilities:US:Chase:Slate                       -21.70 USD
  Expenses:Food:Restaurant                          21.70 USD""",
        'd60da810c0c7b8a57ae16be409c5e17a640a837c1ac29719ebe9f43930463477')


def test_save_entry_slice(example_ledger):
    entry = example_ledger.get_entry('d4a067d229bfda57c8c984d1615da699')
    entry_source, sha256sum = get_entry_slice(entry)
    new_source = """2016-05-03 * "Chichipotle" "Eating out with Joe"
  Expenses:Food:Restaurant                          21.70 USD"""
    filename = entry.meta['filename']
    contents = open(filename).read()

    with pytest.raises(FavaAPIException):
        save_entry_slice(entry, new_source, 'wrong hash')
        assert open(filename).read() == contents

    new_sha256sum = save_entry_slice(entry, new_source, sha256sum)
    assert open(filename).read() != contents
    sha256sum = save_entry_slice(entry, entry_source, new_sha256sum)
    assert open(filename).read() == contents


def test_next_key():
    assert next_key('statement', []) == 'statement'
    assert next_key('statement', ['foo']) == 'statement'
    assert next_key('statement', ['foo', 'statement']) == 'statement-2'
    assert next_key('statement', ['statement', 'statement-2']) == 'statement-3'


def test_leading_space():
    assert leading_space('test') == ''
    assert leading_space('	test') == '	'
    assert leading_space('  test') == '  '
    assert leading_space('    2016-10-31 * "Test" "Test"') == '    '
    assert leading_space('\r\t\r\ttest') == '\r\t\r\t'
    assert leading_space('\ntest') == '\n'


def test_insert_metadata_in_file(tmpdir):
    file_content = dedent("""
        2016-02-26 * "Uncle Boons" "Eating out alone"
            Liabilities:US:Chase:Slate                       -24.84 USD
            Expenses:Food:Restaurant                          24.84 USD
    """)
    samplefile = tmpdir.mkdir('fava_util_file').join('example.beancount')
    samplefile.write(file_content)

    assert samplefile.read() == dedent(file_content)
    assert len(tmpdir.listdir()) == 1

    insert_metadata_in_file(str(samplefile), 1, 'metadata', 'test1')
    assert samplefile.read() == dedent("""
        2016-02-26 * "Uncle Boons" "Eating out alone"
            metadata: "test1"
            Liabilities:US:Chase:Slate                       -24.84 USD
            Expenses:Food:Restaurant                          24.84 USD
    """)

    insert_metadata_in_file(str(samplefile), 1, 'metadata', 'test2')
    assert samplefile.read() == dedent("""
        2016-02-26 * "Uncle Boons" "Eating out alone"
            metadata: "test2"
            metadata: "test1"
            Liabilities:US:Chase:Slate                       -24.84 USD
            Expenses:Food:Restaurant                          24.84 USD
    """)


def test_insert_entry_transaction(tmpdir):
    file_content = dedent("""
        2016-02-26 * "Uncle Boons" "Eating out alone"
            Liabilities:US:Chase:Slate                       -24.84 USD
            Expenses:Food:Restaurant                          24.84 USD

    """)
    samplefile = tmpdir.mkdir('fava_util_file3').join('example.beancount')
    samplefile.write(file_content)

    postings = [
        data.Posting('Liabilities:US:Chase:Slate',
                     amount.Amount(D('-10.00'), 'USD'), None, None, None,
                     None),
        data.Posting('Expenses:Food',
                     amount.Amount(D('10.00'), 'USD'), None, None, None, None),
    ]

    transaction = data.Transaction(None,
                                   datetime.date(2016, 1, 1), '*', 'new payee',
                                   'narr', None, None, postings)

    insert_entry(transaction, [str(samplefile)], [])
    assert samplefile.read() == dedent("""
        2016-02-26 * "Uncle Boons" "Eating out alone"
            Liabilities:US:Chase:Slate                       -24.84 USD
            Expenses:Food:Restaurant                          24.84 USD

        2016-01-01 * "new payee" "narr"
          Liabilities:US:Chase:Slate  -10.00 USD
          Expenses:Food                10.00 USD

    """)

    options = [
        InsertEntryOption(
            datetime.date(2015, 1, 1),
            re.compile('.*:Food'), str(samplefile), 2),
        InsertEntryOption(
            datetime.date(2015, 1, 2),
            re.compile('.*:FOOO'), str(samplefile), 2),
        InsertEntryOption(
            datetime.date(2017, 1, 1),
            re.compile('.*:Food'), str(samplefile), 6),
    ]
    insert_entry(transaction, [str(samplefile)], options)
    assert samplefile.read() == dedent("""
        2016-01-01 * "new payee" "narr"
          Liabilities:US:Chase:Slate  -10.00 USD
          Expenses:Food                10.00 USD

        2016-02-26 * "Uncle Boons" "Eating out alone"
            Liabilities:US:Chase:Slate                       -24.84 USD
            Expenses:Food:Restaurant                          24.84 USD

        2016-01-01 * "new payee" "narr"
          Liabilities:US:Chase:Slate  -10.00 USD
          Expenses:Food                10.00 USD

    """)

    options = [
        InsertEntryOption(
            datetime.date(2015, 1, 1),
            re.compile('.*:Slate'), str(samplefile), 5),
        InsertEntryOption(
            datetime.date(2015, 1, 2),
            re.compile('.*:FOOO'), str(samplefile), 2),
    ]
    insert_entry(transaction, [str(samplefile)], options)
    assert samplefile.read() == dedent("""
        2016-01-01 * "new payee" "narr"
          Liabilities:US:Chase:Slate  -10.00 USD
          Expenses:Food                10.00 USD
        2016-01-01 * "new payee" "narr"
          Liabilities:US:Chase:Slate  -10.00 USD
          Expenses:Food                10.00 USD


        2016-02-26 * "Uncle Boons" "Eating out alone"
            Liabilities:US:Chase:Slate                       -24.84 USD
            Expenses:Food:Restaurant                          24.84 USD

        2016-01-01 * "new payee" "narr"
          Liabilities:US:Chase:Slate  -10.00 USD
          Expenses:Food                10.00 USD

    """)


def test_render_entries(example_ledger):
    entry1 = example_ledger.get_entry('4af0865b1371c1b5576e9ff7f7d20dc9')
    entry2 = example_ledger.get_entry('85f3ba57bf52dc1bd6c77ef3510223ae')

    file_content = dedent("""\
        2016-04-09 * "Uncle Boons" "" #trip-new-york-2016
          Liabilities:US:Chase:Slate                       -52.22 USD
          Expenses:Food:Restaurant                          52.22 USD

        2016-05-04 * "BANK FEES" "Monthly bank fee"
          Assets:US:BofA:Checking                           -4.00 USD
          Expenses:Financial:Fees                            4.00 USD
    """)

    assert file_content == "\n".join(
        example_ledger.file.render_entries([entry1, entry2]))
