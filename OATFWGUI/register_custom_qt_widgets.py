from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

from qbusyindicatorgoodbad import QBusyIndicatorGoodBad
from qwarningbannerholder import QWarningBannerHolder

"""
Set the environment variable PYSIDE_DESIGNER_PLUGINS to this directory and load the plugin,
both in the app and with pyside6-designer

"""

if __name__ == '__main__':
    # See RegisteredCustomWidget for this factory paradigm
    qbusyindicatorgoodbad = QBusyIndicatorGoodBad.factory()
    QPyDesignerCustomWidgetCollection.registerCustomWidget(
        qbusyindicatorgoodbad,
        module=qbusyindicatorgoodbad.designer_module,  # idk what this actually affects
        tool_tip=qbusyindicatorgoodbad.designer_tooltip,
        xml=qbusyindicatorgoodbad.designer_dom_xml,
    )
    qwarningbannerholder = QWarningBannerHolder.factory()
    QPyDesignerCustomWidgetCollection.registerCustomWidget(
        qwarningbannerholder,
        module=qwarningbannerholder.designer_module,  # idk what this actually affects
        tool_tip=qwarningbannerholder.designer_tooltip,
        xml=qwarningbannerholder.designer_dom_xml,
    )
