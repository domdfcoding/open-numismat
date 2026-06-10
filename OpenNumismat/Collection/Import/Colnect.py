import json
import pprint
import urllib.request

from OpenNumismat.Tools.Gui import createIcon
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import *

from OpenNumismat import version
from OpenNumismat.Settings import Settings
from OpenNumismat.Tools.DialogDecorators import storeDlgSizeDecorator

colnectAvailable = True

try:
    from OpenNumismat.private_keys import NUMISTA_API_KEY
except ImportError:
    print('Importing from Numista not available')
    colnectAvailable = False


@storeDlgSizeDecorator
class ColnectDialog(QDialog):
    HEIGHT = 40

    def __init__(self, model, parent=None):
        super().__init__(parent,
                         Qt.WindowCloseButtonHint | Qt.WindowSystemMenuHint)
        self.setWindowIcon(createIcon('numista.png'))
        self.setWindowTitle("Numista Import")

        self.model = model
        self.autoclose = Settings()['colnect_autoclose']

        layout = QFormLayout()
        layout.setRowWrapPolicy(QFormLayout.WrapLongRows)

        self.numistaLabel = QLabel(self.tr("Paste a <a href=\"https://en.numista.com/\">Numista</a> URL to add to the collection"))
        self.numistaLabel.setTextFormat(Qt.RichText)
        self.numistaLabel.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.numistaLabel.setOpenExternalLinks(True)
        font = self.numistaLabel.font()
        font.setPointSize(11)
        self.numistaLabel.setFont(font)
        layout.addRow(self.numistaLabel)

        self.textbox = QLineEdit(self)
        # self.textbox.resize(280,40)
        self.textbox.textChanged.connect(self.onTextboxChange)
        layout.addRow(self.textbox)

        self.addButton = QPushButton(self.tr("Add"))
        self.addButton.setEnabled(False)
        self.addCloseButton = QPushButton(self.tr("Add and close"))
        self.addCloseButton.setEnabled(False)
        if self.autoclose:
            self.addCloseButton.setDefault(True)
        else:
            self.addButton.setDefault(True)

        buttonBox = QDialogButtonBox(Qt.Horizontal, self)
        buttonBox.addButton(self.addButton, QDialogButtonBox.ActionRole)
        buttonBox.addButton(self.addCloseButton, QDialogButtonBox.ActionRole)
        buttonBox.addButton(QDialogButtonBox.Close)
        buttonBox.clicked.connect(self.clicked)

        vlayout = QVBoxLayout()
        vlayout.addLayout(layout)
        vlayout.addWidget(buttonBox)

        self.setLayout(vlayout)

    def onTextboxChange(self):
        if self.textbox.text():
            self.addButton.setEnabled(True)
            self.addCloseButton.setEnabled(True)
        else:
            self.addButton.setEnabled(False)
            self.addCloseButton.setEnabled(False)

    def addCoin(self, close):
                
        item_url = self.textbox.text()

        parts = urllib.parse.urlparse(item_url)
        item_id: str = parts.path.strip("/")
        assert item_id.isdigit()
        print(item_id)

        req = urllib.request.Request(f"https://api.numista.com/v3/types/{item_id}", headers={'User-Agent': version.AppName, "Numista-API-Key": NUMISTA_API_KEY})
        raw_data = urllib.request.urlopen(req).read().decode()
        data = json.loads(raw_data)

        newRecord = self.model.record()
        self.makeItem(data, newRecord)
        if close:
            self.accept()
        self.model.addCoin(newRecord, self)
  

    def setValue(self, record, field: str, data: dict, key: str = None, skey: str = None):
        if key is None:
            key = field

        if key in data:
            value = data.pop(key)

            if skey is not None and skey in value:
                value = value[skey]

            record.setValue(field, value)

    def makeItem(self, data: dict, record):

        print(record)
        print(pprint.pprint(data))

        self.setValue(record, "title", data)
        # TODO: Region; lookup from country?
        self.setValue(record, "country", data, "issuer", "name")
        # Period
        # Emitent
        
        if "ruler" in data:
            record.setValue("ruler", data.pop("ruler")[0]["name"])

        if "value" in data:
            value = data.pop("value")
            self.setValue(record, "value", value, "numeric_value")
            self.setValue(record, "unit", value, "currency", "name")  # Or full_name?
        
        if "min_year" in data and "max_year" in data:
            min_year = data.pop("min_year")
            max_year = data.pop("max_year")
            record.setValue("year", min_year)
            record.setValue("dateemis", f"{min_year} - {max_year}")

        if "mints" in data:
            record.setValue("mint", data.pop("mints")[0]["name"])

        self.setValue(record, "mintmark", data, "issue", "mintLetter")
        self.setValue(record, "type", data)  # TODO: lookup, or use 'object_type'
        # Series
        self.setValue(record, "subject", data, "commemorated_topic")
        self.setValue(record, "material", data, "composition", "text")
        # Fineness

        self.setValue(record, "weight", data)
        self.setValue(record, "thickness", data)
        self.setValue(record, "thickness", data, "size2")
        self.setValue(record, "diameter", data, "size")
        self.setValue(record, "shape", data)
        self.setValue(record, "obvrev", data, "orientation")  # TODO: lookup ( "Medallic (0°)", "Coin (180°)", "90°")
        self.setValue(record, "issuedate", data, "issue_terms", "issue_date")
        # self.setValue(record, "note", data, "comments")  # TODO: is HTML
        
        for side in ("obverse", "reverse"):
            if side in data:
                self.setObvRev(record, data.pop(side), side)

        if "edge" in data:
            edge = data.pop("edge")
            self.setValue(record, "edge", edge, "description")
            self.setValue(record, "edgelabel", edge, "lettering")
            if "picture" in edge:
                img = self.getImgBytes(edge.pop("picture"))
                if img:
                    record.setValue("edgeimg", img)
        
        
        references: list = data.pop("references")
        for idx, ref in enumerate(references):
            record.setValue(f"catalognum{idx+1}", f"{ref['catalogue']['code']}# {ref['number']}")
        
        # record.setValue("url", f"https://en.numista.com/{data.pop('id')}")
        self.setValue(record, "url", data)



        print(pprint.pprint(data))

        


    def setObvRev(self, record, data: dict, obvrev: str):
        
        desc = (data.pop("description", '') + "\n\n" + data.pop("lettering", '')).strip()
        
        if desc:
            record.setValue(f"{obvrev}design", desc)

        # record.setValue(f"{obvrev}designer", )

        if "engravers" in data or "designers" in data:
            record.setValue(f"{obvrev}engraver", " and ".join([*data.pop("engravers", []), *data.pop("designers", [])]))

        if "picture" in data:
            img = self.getImgBytes(data.pop("picture"))
            if img:
                record.setValue(f"{obvrev}img", img)

    def getImgBytes(self, url: str):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': version.AppName})
            img = urllib.request.urlopen(req, timeout=30).read()
            return img
        except ImportError:
            return None


    def clicked(self, button):
        if button == self.addButton:
            print("Import from URL", self.textbox.text())
            self.addCoin(False)
        elif button == self.addCloseButton:
            print("Import from URL", self.textbox.text())
            self.addCoin(True)

            self.accept()
        else:
            self.accept()
