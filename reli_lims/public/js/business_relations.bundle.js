frappe.provide("reli_lims.relations");

(function () {
    const language = () => String(
        frappe.boot?.lang || frappe.local?.lang || document.documentElement.lang || ""
    ).toLowerCase();
    const apply_service_item_labels = () => {
        if (!language().startsWith("zh")) return;
        frappe._messages = frappe._messages || {};
        Object.assign(frappe._messages, {
            Item: "服务商品",
            Items: "服务商品",
            "Item Name": "服务商品名称",
            "Item Code": "服务商品编码",
            "Add Item": "添加服务商品",
        });
    };

    const apply_service_item_navigation = () => {
        if (!language().startsWith("zh")) return;
        document.querySelectorAll("a.item-anchor[href]").forEach(anchor => {
            if (!/\/desk\/(?:stock\/)?item$/.test(anchor.getAttribute("href") || "")) return;
            const label = anchor.querySelector(".sidebar-item-label");
            if (label && ["选项", "Item"].includes(label.textContent.trim())) {
                label.textContent = "服务商品";
            }
        });
    };

    const apply_labels = () => {
        apply_service_item_labels();
        apply_service_item_navigation();
    };

    apply_labels();
    document.addEventListener("DOMContentLoaded", () => {
        apply_labels();
        const dock = document.getElementById("desk-dock");
        if (dock && window.MutationObserver) {
            new MutationObserver(apply_service_item_navigation).observe(dock, {
                childList: true,
                subtree: true,
            });
        }
        window.setTimeout(apply_labels, 500);
    });
})();

(function () {
    const relations = reli_lims.relations;
    const page_size = 10;

    function link_button(label, doctype, name) {
        if (!name) return $("<span>").text("—");
        return $("<button type='button' class='btn btn-link p-0 text-left'>")
            .text(label || name)
            .on("click", () => frappe.set_route("Form", doctype, name));
    }

    function summary_card(label, value) {
        return $("<div class='border rounded px-3 py-2'>").append(
            $("<div class='text-muted small'>").text(__(label)),
            $("<div class='h5 mb-0'>").text(value || 0),
        );
    }

    function render_cell(column, row) {
        const td = $("<td>");
        const value = column.value ? column.value(row) : row[column.key];
        if (column.link) {
            const name = column.link.name(row);
            td.append(link_button(value, column.link.doctype, name));
        } else {
            td.text(value || "—");
        }
        return td;
    }

    relations.render_table = function (container, options, state) {
        const rows = options.rows || [];
        const pages = Math.max(1, Math.ceil(rows.length / page_size));
        const page = Math.min(state.pages[options.key] || 0, pages - 1);
        state.pages[options.key] = page;

        const section = $("<div class='mb-4'>").appendTo(container);
        $("<h6 class='mb-2'>").text(`${__(options.title)} · ${rows.length}`).appendTo(section);
        if (!rows.length) {
            $("<p class='text-muted mb-0'>").text(__("暂无记录")).appendTo(section);
            return;
        }

        const table = $("<table class='table table-sm table-bordered align-middle'>").appendTo(section);
        const head = $("<tr>").appendTo($("<thead>").appendTo(table));
        options.columns.forEach(column => $("<th scope='col'>").text(__(column.label)).appendTo(head));
        const body = $("<tbody>").appendTo(table);
        rows.slice(page * page_size, (page + 1) * page_size).forEach(row => {
            const tr = $("<tr>").appendTo(body);
            options.columns.forEach(column => tr.append(render_cell(column, row)));
        });

        if (pages > 1) {
            const pager = $("<div class='d-flex align-items-center gap-2'>").appendTo(section);
            $("<button type='button' class='btn btn-default btn-xs'>").text(__("上一页"))
                .prop("disabled", page === 0)
                .on("click", () => { state.pages[options.key] = page - 1; options.refresh(); })
                .appendTo(pager);
            $("<span class='text-muted small'>").text(__("第 {0} / {1} 页", [page + 1, pages]))
                .appendTo(pager);
            $("<button type='button' class='btn btn-default btn-xs'>").text(__("下一页"))
                .prop("disabled", page >= pages - 1)
                .on("click", () => { state.pages[options.key] = page + 1; options.refresh(); })
                .appendTo(pager);
        }
    };

    relations.render_filters = function (container, data, state, refresh) {
        const bar = $("<div class='row g-2 align-items-end mb-3'>").appendTo(container);
        const add_group = (width, label, control) => {
            const group = $(`<div class='col-sm-${width}'>`).appendTo(bar);
            $("<label class='text-muted small d-block mb-1'>").text(__(label)).appendTo(group);
            control.appendTo(group);
        };

        const search = $("<input type='search' class='form-control form-control-sm' placeholder='输入中文名称、编码或能力范围'>")
            .val(state.text || "");
        search.on("input", frappe.utils.debounce(() => {
            state.text = search.val().trim();
            Object.keys(state.pages).forEach(key => { state.pages[key] = 0; });
            refresh();
        }, 200));
        add_group(4, "搜索", search);

        const add_select = (width, label, key, rows, label_field) => {
            const select = $("<select class='form-control form-control-sm'>");
            $("<option value=''>").text(__("全部") + __(label)).appendTo(select);
            rows.forEach(row => $("<option>").val(row.name).text(row[label_field] || row.name).appendTo(select));
            select.val(state[key] || "").on("change", () => {
                state[key] = select.val();
                Object.keys(state.pages).forEach(page => { state.pages[page] = 0; });
                refresh();
            });
            add_group(width, label, select);
        };

        add_select(3, "检测项目", "project", data.projects || [], "project_name");
        add_select(3, "检测依据（标准/方法）", "standard", data.standards || [], "full_name");
        add_select(2, "实验室", "laboratory", data.laboratories || [], "laboratory_name");

        $("<div class='col-sm-12'>").append(
            $("<button type='button' class='btn btn-default btn-xs'>").text(__("清除筛选"))
                .on("click", () => {
                    state.text = "";
                    state.project = "";
                    state.standard = "";
                    state.laboratory = "";
                    Object.keys(state.pages).forEach(key => { state.pages[key] = 0; });
                    search.val("");
                    bar.find("select").val("");
                    refresh();
                }),
        ).appendTo(bar);
    };

    relations.render_tabs = function (container, state, tabs, refresh) {
        const nav = $("<div class='mb-3 d-flex flex-wrap gap-2'>").appendTo(container);
        const buttons = {};
        tabs.forEach(tab => {
            const button = $("<button type='button' class='btn btn-sm btn-default'>").appendTo(nav);
            buttons[tab.key] = button;
            button.on("click", () => {
                state.tab = tab.key;
                refresh();
            });
        });
        return counts => {
            tabs.forEach(tab => {
                buttons[tab.key]
                    .toggleClass("btn-primary", state.tab === tab.key)
                    .toggleClass("btn-default", state.tab !== tab.key)
                    .text(`${__(tab.label)} · ${counts[tab.key] || 0}`);
            });
        };
    };

    relations.capability_columns = function (show_object) {
        const columns = [
            {label: "实验室", value: row => row.laboratory_label,
                link: {doctype: "Laboratory Profile", name: row => row.laboratory}},
            {label: "检测项目", value: row => row.project_label,
                link: {doctype: "Test Project", name: row => row.test_project}},
            {label: "检测依据（标准/方法）", value: row => row.standard_label,
                link: {doctype: "Test Standard", name: row => row.test_standard}},
            {label: "能力范围", key: "capability_scope"},
            {label: "限制说明", key: "limitation"},
            {label: "实验室能力", value: row => row.name,
                link: {doctype: "Laboratory Capability", name: row => row.name}},
        ];
        if (show_object) columns.splice(3, 0, {label: "检测对象", value: row => row.object_label});
        return columns;
    };

    relations.item_columns = function () {
        return [
            {label: "服务商品", value: row => row.item_name,
                link: {doctype: "Item", name: row => row.name}},
            {label: "服务商品编码", key: "item_code"},
            {label: "检测项目", value: row => row.project_label,
                link: {doctype: "Test Project", name: row => row.custom_reli_test_project}},
        ];
    };

    relations.object_data = function (data, state) {
        const term = (state.text || "").toLowerCase();
        const includes = (...values) => !term || values.some(value => String(value || "").toLowerCase().includes(term));
        const standard_projects = new Set(
            (data.standards || []).find(row => row.name === state.standard)?.project_ids || [],
        );
        const laboratory_projects = new Set(
            (data.capabilities || []).filter(row => row.laboratory === state.laboratory)
                .map(row => row.test_project),
        );
        const projects = (data.projects || []).filter(row =>
            includes(row.project_name, row.name, row.category) &&
            (!state.project || row.name === state.project) &&
            (!state.standard || (row.standard_ids || []).includes(state.standard)) &&
            (!state.laboratory || (row.laboratory_ids || []).includes(state.laboratory)),
        );
        const standards = (data.standards || []).filter(row =>
            includes(row.full_name, row.standard_code, row.title, row.version, row.basis_type) &&
            (!state.project || (row.project_ids || []).includes(state.project)) &&
            (!state.standard || row.name === state.standard) &&
            (!state.laboratory || (row.laboratory_ids || []).includes(state.laboratory)),
        );
        const capabilities = (data.capabilities || []).filter(row =>
            includes(row.project_label, row.object_label, row.standard_label, row.laboratory_label,
                row.product_scope, row.project_parameter, row.capability_scope, row.limitation, row.source_row) &&
            (!state.project || row.test_project === state.project) &&
            (!state.standard || row.test_standard === state.standard) &&
            (!state.laboratory || row.laboratory === state.laboratory),
        );
        const items = (data.items || []).filter(row =>
            includes(row.item_name, row.item_code, row.project_label) &&
            (!state.project || row.custom_reli_test_project === state.project) &&
            (!state.standard || standard_projects.has(row.custom_reli_test_project)) &&
            (!state.laboratory || laboratory_projects.has(row.custom_reli_test_project)),
        );
        return {projects, standards, capabilities, items};
    };

    relations.mount_object = function (frm) {
        const wrapper = frm.fields_dict.relations_html?.$wrapper;
        if (!wrapper) return;
        wrapper.empty();
        if (frm.is_new()) {
            wrapper.text(__("保存检测对象后可查看关联项目、依据、能力和服务商品。"));
            return;
        }
        $("<p class='text-muted'>").text(__("以下关系均从现有检测项目关联和实验室能力实时查询，不复制业务数据。"))
            .appendTo(wrapper);
        frappe.call({
            method: "reli_lims.business_relations.test_object_relations",
            args: {test_object: frm.doc.name},
        }).then(({message}) => {
            const state = {text: "", project: "", standard: "", laboratory: "", tab: "projects", pages: {}};
            const root = $("<div>").appendTo(wrapper);
            const summary = $("<div class='d-flex flex-wrap gap-2 mb-3'>").appendTo(root);
            [
                ["检测项目", message.counts.projects], ["检测依据", message.counts.standards],
                ["实验室能力", message.counts.capabilities], ["实验室", message.counts.laboratories],
                ["服务商品", message.counts.items],
            ].forEach(([label, value]) => summary.append(summary_card(label, value)));

            const filter_host = $("<div>").appendTo(root);
            const tabs_host = $("<div>").appendTo(root);
            const table_host = $("<div>").appendTo(root);
            let update_tabs;
            const refresh = () => {
                const filtered = relations.object_data(message, state);
                const counts = {
                    projects: filtered.projects.length,
                    standards: filtered.standards.length,
                    capabilities: filtered.capabilities.length,
                    items: filtered.items.length,
                };
                update_tabs(counts);
                table_host.empty();
                const options = {
                    projects: {
                        key: "projects", title: "关联检测项目", rows: filtered.projects,
                        columns: [
                            {label: "检测项目", value: row => row.project_name,
                                link: {doctype: "Test Project", name: row => row.name}},
                            {label: "项目分类", key: "category"},
                            {label: "检测依据", value: row => (row.standard_ids || []).length},
                            {label: "实验室能力", key: "capability_count"},
                            {label: "服务商品", key: "item_count"},
                        ],
                    },
                    standards: {
                        key: "standards", title: "关联检测依据（标准/方法）", rows: filtered.standards,
                        columns: [
                            {label: "检测依据（标准/方法）", value: row => row.full_name,
                                link: {doctype: "Test Standard", name: row => row.name}},
                            {label: "依据类型", key: "basis_type"},
                            {label: "状态", key: "status"},
                            {label: "关联项目", key: "project_count"},
                            {label: "实验室能力", key: "capability_count"},
                        ],
                    },
                    capabilities: {
                        key: "capabilities", title: "关联实验室能力", rows: filtered.capabilities,
                        columns: relations.capability_columns(false),
                    },
                    items: {
                        key: "items", title: "可销售服务商品", rows: filtered.items,
                        columns: relations.item_columns(),
                    },
                }[state.tab];
                options.refresh = refresh;
                relations.render_table(table_host, options, state);
            };
            relations.render_filters(filter_host, message, state, refresh);
            update_tabs = relations.render_tabs(tabs_host, state, [
                {key: "projects", label: "检测项目"},
                {key: "standards", label: "检测依据（标准/方法）"},
                {key: "capabilities", label: "实验室能力"},
                {key: "items", label: "服务商品"},
            ], refresh);
            refresh();
        });
    };

    relations.mount_project = function (frm) {
        const wrapper = frm.fields_dict.relations_html?.$wrapper;
        if (!wrapper) return;
        wrapper.empty();
        if (frm.is_new()) {
            wrapper.text(__("保存检测项目后可查看关联实验室能力与服务商品。"));
            return;
        }
        frappe.call({
            method: "reli_lims.business_relations.test_project_relations",
            args: {test_project: frm.doc.name},
        }).then(({message}) => {
            const root = $("<div>").appendTo(wrapper);
            const summary = $("<div class='d-flex flex-wrap gap-2 mb-3'>").appendTo(root);
            [
                ["检测对象", message.counts.objects], ["检测依据", message.counts.standards],
                ["实验室能力", message.counts.capabilities], ["服务商品", message.counts.items],
            ].forEach(([label, value]) => summary.append(summary_card(label, value)));
            const state = {pages: {}};
            const refresh = () => {
                root.find(".reli-project-relations").remove();
                const host = $("<div class='reli-project-relations'>").appendTo(root);
                relations.render_table(host, {
                    key: "capabilities", title: "关联实验室能力", rows: message.capabilities,
                    columns: relations.capability_columns(false), refresh,
                }, state);
                relations.render_table(host, {
                    key: "items", title: "关联服务商品", rows: message.items,
                    columns: relations.item_columns(), refresh,
                }, state);
            };
            refresh();
        });
    };

    relations.mount_standard = function (frm) {
        const wrapper = frm.fields_dict.relations_html?.$wrapper;
        if (!wrapper) return;
        wrapper.empty();
        if (frm.is_new()) {
            wrapper.text(__("保存检测依据后可查看关联检测项目、实验室能力与服务商品。"));
            return;
        }
        frappe.call({
            method: "reli_lims.business_relations.test_standard_relations",
            args: {test_standard: frm.doc.name},
        }).then(({message}) => {
            const root = $("<div>").appendTo(wrapper);
            const summary = $("<div class='d-flex flex-wrap gap-2 mb-3'>").appendTo(root);
            [
                ["检测项目", message.counts.projects], ["实验室能力", message.counts.capabilities],
                ["实验室", message.counts.laboratories], ["服务商品", message.counts.items],
            ].forEach(([label, value]) => summary.append(summary_card(label, value)));
            const state = {pages: {}};
            const refresh = () => {
                root.find(".reli-standard-relations").remove();
                const host = $("<div class='reli-standard-relations'>").appendTo(root);
                relations.render_table(host, {
                    key: "projects", title: "关联检测项目", rows: message.projects,
                    columns: [
                        {label: "检测项目", value: row => row.project_name,
                            link: {doctype: "Test Project", name: row => row.name}},
                        {label: "项目分类", key: "category"},
                        {label: "归类状态", key: "classification_status"},
                    ], refresh,
                }, state);
                relations.render_table(host, {
                    key: "capabilities", title: "关联实验室能力", rows: message.capabilities,
                    columns: relations.capability_columns(true), refresh,
                }, state);
                relations.render_table(host, {
                    key: "items", title: "关联服务商品", rows: message.items,
                    columns: relations.item_columns(), refresh,
                }, state);
            };
            refresh();
        });
    };

    relations.mount_item = function (frm) {
        const wrapper = frm.fields_dict.custom_reli_business_relations?.$wrapper;
        if (!wrapper) return;
        wrapper.empty();
        if (frm.is_new()) return;
        frappe.call({
            method: "reli_lims.business_relations.item_relations",
            args: {item: frm.doc.name},
        }).then(({message}) => {
            if (!message.project) {
                $("<p class='text-muted mb-0'>").text(__("尚未关联检测项目。")).appendTo(wrapper);
                return;
            }
            const project = message.project;
            const summary = $("<div class='border rounded p-3'>").appendTo(wrapper);
            summary.append($("<div class='text-muted small'>").text(__("关联检测项目")));
            summary.append($("<div class='h5 mb-2'>")
                .append(link_button(project.project_name, "Test Project", project.name)));
            const counts = $("<div class='d-flex flex-wrap gap-2'>").appendTo(summary);
            [
                ["检测对象", message.counts.objects], ["检测依据", message.counts.standards],
                ["实验室能力", message.counts.capabilities], ["服务商品", message.counts.service_items],
            ].forEach(([label, value]) => counts.append(summary_card(label, value)));
        });
    };
})();
