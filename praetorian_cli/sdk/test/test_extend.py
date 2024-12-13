import pytest

from praetorian_cli.sdk.chariot import extend


@pytest.mark.coherence
class TestExtend:

    def test_both_empty(self):
        assert extend(dict(), dict()) == dict()

    def test_empty_accumulate(self):
        assert extend(dict(), dict(c=[1, 2], d=[3, 4])) == dict(c=[1, 2], d=[3, 4])

    def test_empty_new(self):
        assert extend(dict(c=[1, 2], d=[3, 4]), dict()) == dict(c=[1, 2], d=[3, 4])

    def test_no_overlap(self):
        assert extend(dict(a=[1, 2], b=[4, 5]), dict(c=[7, 8])) == dict(a=[1, 2], b=[4, 5], c=[7, 8])

    def test_overlap(self):
        assert extend(dict(a=[1, 2], b=[5, 6]), dict(c=[7, 8], a=[3, 4])) == dict(a=[1, 2, 3, 4], b=[5, 6], c=[7, 8])

    def test_dict_in_new(self):
        assert extend(dict(a=[1], b=[2]), dict(c=dict(d=[3], e=[4]))) == dict(a=[1], b=[2], c=dict(d=[3], e=[4]))

    def test_dict_in_accumulate(self):
        assert extend(dict(c=dict(d=[3], e=[4])), dict(a=[1], b=[2])) == dict(a=[1], b=[2], c=dict(d=[3], e=[4]))

    def test_extend_array_in_dict(self):
        assert extend(dict(c=dict(d=[3], e=[4])), dict(c=dict(d=[5]))) == dict(c=dict(d=[3, 5], e=[4]))

    def test_new_array_in_new(self):
        assert extend(dict(c=dict(e=[4])), dict(c=dict(d=[5]))) == dict(c=dict(d=[5], e=[4]))

    def test_new_dict_in_new(self):
        assert extend(dict(a=[1]), dict(b=dict(c=[5]))) == dict(a=[1], b=dict(c=[5]))

    def test_unexpected_data_type(self):
        assert extend(dict(), dict(a=dict(b="1", c=[1, 2]))) == dict(a=dict(c=[1, 2]))

    def test_deeper(self):
        assert (extend(dict(a=dict(b=dict(c=dict(d=[1]), e=[3]), f=[1])),
                       dict(a=dict(b=dict(c=dict(d=[2]), e=[4])))) ==
                dict(a=dict(b=dict(c=dict(d=[1, 2]), e=[3, 4]), f=[1])))
