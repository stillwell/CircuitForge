"""Vendor URL resolver tests."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestVendorLinks(unittest.TestCase):
    def test_jlcpcb_yields_lcsc_and_jlcpcb(self):
        from circuitforge.database import vendor_links, ComponentRecord
        r = ComponentRecord(source="jlcpcb", source_id="C1234567",
                            mpn="LM358DR", manufacturer="TI",
                            datasheet_url="https://example.com/ds.pdf")
        links = vendor_links(r)
        kinds = [lk["kind"] for lk in links]
        self.assertIn("lcsc", kinds)
        self.assertIn("jlcpcb", kinds)
        self.assertIn("datasheet", kinds)
        self.assertIn("octopart", kinds)            # MPN cross-ref
        # URL shapes
        lcsc = next(lk for lk in links if lk["kind"] == "lcsc")
        self.assertIn("lcsc.com/product-detail/C1234567", lcsc["url"])
        jlc = next(lk for lk in links if lk["kind"] == "jlcpcb")
        self.assertIn("jlcpcb.com/partdetail/1234567", jlc["url"])

    def test_digikey_uses_mpn(self):
        from circuitforge.database import vendor_links, ComponentRecord
        r = ComponentRecord(source="digikey", source_id="DK-PART",
                            mpn="ATMEGA328P-PU")
        links = vendor_links(r)
        dk = next(lk for lk in links if lk["kind"] == "digikey")
        self.assertIn("ATMEGA328P-PU", dk["url"])

    def test_mouser_uses_mpn(self):
        from circuitforge.database import vendor_links, ComponentRecord
        r = ComponentRecord(source="mouser", source_id="X",
                            mpn="STM32F411CEU6")
        links = vendor_links(r)
        m = next(lk for lk in links if lk["kind"] == "mouser")
        self.assertIn("STM32F411CEU6", m["url"])

    def test_octopart_record_no_self_xref(self):
        """A record already from Octopart shouldn't get a second cross-ref."""
        from circuitforge.database import vendor_links, ComponentRecord
        r = ComponentRecord(source="octopart", source_id="abc", mpn="LM358")
        links = vendor_links(r)
        octopart_links = [lk for lk in links if lk["kind"] == "octopart"]
        self.assertEqual(len(octopart_links), 1)   # only the primary, no extra xref

    def test_kicad_links_to_gitlab(self):
        from circuitforge.database import vendor_links, ComponentRecord
        r = ComponentRecord(source="kicad", source_id="Amplifier_Operational:LM358",
                            symbol_lib="Amplifier_Operational", name="LM358")
        links = vendor_links(r)
        k = next(lk for lk in links if lk["kind"] == "kicad")
        self.assertIn("gitlab.com/kicad/libraries/kicad-symbols", k["url"])
        self.assertIn("Amplifier_Operational.kicad_sym", k["url"])

    def test_local_only_datasheet(self):
        """A local record with no datasheet/MPN yields no vendor links."""
        from circuitforge.database import vendor_links, ComponentRecord
        r = ComponentRecord(source="local", source_id="NE555",
                            mpn="", datasheet_url="")
        links = vendor_links(r)
        self.assertEqual(links, [])

    def test_link_dict_shape(self):
        """Each link has the keys the templates/Qt code expects."""
        from circuitforge.database import vendor_links, ComponentRecord
        r = ComponentRecord(source="jlcpcb", source_id="C100",
                            mpn="X", datasheet_url="https://x")
        for lk in vendor_links(r):
            self.assertEqual(set(lk.keys()),
                             {"kind", "label", "url", "color", "icon"})
            self.assertTrue(lk["url"].startswith("http"))
            self.assertTrue(lk["color"].startswith("#"))


if __name__ == "__main__":
    unittest.main()
