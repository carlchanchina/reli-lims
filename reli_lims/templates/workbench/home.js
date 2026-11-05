const host = root_element.getRootNode().host;
const widget = host?.closest(".custom-block-widget-box");
if (widget) widget.dataset.reliHome = "1";
