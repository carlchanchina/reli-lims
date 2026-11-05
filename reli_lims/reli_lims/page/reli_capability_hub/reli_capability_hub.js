frappe.pages["reli-capability-hub"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper, title: __("能力查询"), single_column: true,
    });
    const body = $(page.body);

    const open_capabilities = async () => {
        await frappe.require("capability_grid.bundle.js");
        await frappe.require("/assets/reli_lims/js/capability_selector.js");
        return reli_lims.capabilities.open({mode: "catalog"});
    };

    page.set_primary_action(__("新增检测项目"), () => frappe.new_doc("Test Project"));
    page.add_inner_button(__("添加实验室能力"), () => frappe.new_doc("Laboratory Capability"));
    page.add_inner_button(__("筛选全部能力"), open_capabilities);

    $("<p class='text-muted'>")
        .text(__("检测项目是全平台统一主数据；实验室能力按实验室、对象、依据和限制范围保留独立明细。"))
        .appendTo(body);

    frappe.call("reli_lims.capability_catalog.dashboard").then(({message}) => {
        const counts = $("<div class='reli-capability-counts d-flex flex-wrap gap-2 mb-4'>").appendTo(body);
        for (const [label, value] of [
            [__("检测项目"), message.projects], [__("已归类"), message.classified],
            [__("待分类"), message.pending], [__("检测对象"), message.objects],
            [__("检测依据"), message.standards], [__("实验室"), message.laboratories],
            [__("实验室能力"), message.capabilities], [__("CNAS 能力"), message.cnas_capabilities],
            [__("未归类能力"), message.unclassified_capabilities], [__("服务商品"), message.service_items],
        ]) {
            $("<div class='border rounded px-3 py-2'>").append(
                $("<div class='text-muted small'>").text(label),
                $("<div class='h4 mb-0'>").text(value || 0),
            ).appendTo(counts);
        }
    });

    const nav = $("<div class='row mb-4'>").appendTo(body);
    const entries = [
        [__("检测项目库"), __("统一检测项目、分类、别名和条件模板"), () => frappe.set_route("List", "Test Project")],
        [__("全部能力明细"), __("按项目、对象、依据和实验室筛选"), open_capabilities],
        [__("检测对象分类"), __("受控检测对象及分类、别名"), () => frappe.set_route("List", "Test Object")],
        [__("检测依据（标准/方法）"), __("标准编号、名称、版本与依据类型"), () => frappe.set_route("List", "Test Standard")],
        [__("实验室管理"), __("实验室资料、能力来源与服务商品"), () => frappe.set_route("List", "Laboratory Profile")],
        [__("能力来源"), __("来源文件与原始结构化能力明细"), () => frappe.set_route("List", "Capability Source")],
        [__("服务商品关联"), __("以中文服务名称关联检测项目与 Item"), () => {
            frappe.route_options = {is_stock_item: 0, is_sales_item: 1};
            frappe.set_route("List", "Item");
        }],
    ];
    for (const [title, description, action] of entries) {
        const column = $("<div class='col-sm-6 col-lg-4 mb-3'>").appendTo(nav);
        const card = $("<button type='button' class='btn btn-default text-left w-100 h-100 p-3'>")
            .on("click", action).appendTo(column);
        $("<div class='h5'>").text(title).appendTo(card);
        $("<div class='text-muted'>").text(description).appendTo(card);
    }

    $("<div class='border-top pt-3'>").append(
        $("<h5>").text(__("操作边界")),
        $("<p class='text-muted mb-0'>").text(__("新增检测项目用于建立公共项目字典；添加实验室能力用于登记某个实验室针对对象、项目、依据和限制范围的具体能力。两者不会互相替代。")),
    ).appendTo(body);
};
