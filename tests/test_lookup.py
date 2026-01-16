import os
import tempfile
from phone_finder.lookup import load_contacts_csv, find_name_local


def test_local_lookup():
    # create a temporary CSV file
    content = "name,phone\nTest Person,+1 415 555 2671\n"
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as tf:
        tf.write(content)
        path = tf.name

    try:
        contacts = load_contacts_csv(path, default_region='US')
        assert isinstance(contacts, dict)
        name = find_name_local('+1 415 555 2671', contacts, default_region='US')
        assert name == 'Test Person'
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass
