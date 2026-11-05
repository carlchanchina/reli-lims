const host = root_element.getRootNode().host;
const widget = host?.closest(".custom-block-widget-box");
if (widget) widget.dataset.reliHome = "1";
for (const anchor of root_element.querySelectorAll('a[href^="/desk/"]')) {
    anchor.addEventListener("click", event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return;
        event.preventDefault();
        event.stopPropagation();
        const target = new URL(anchor.getAttribute("href"), window.location.origin);
        frappe.route_options = Object.fromEntries(target.searchParams);
        frappe.set_route(target.pathname);
    });
}
