# 文档输出

本模块在 Reli LIMS 内提供跨单据的文件模板输出。源单据固定为 ERPNext `Quotation` 和现有 `Test Request`、`Test Report`；不新增业务 DocType。

## 使用

保存单据后，点击“生成文档”，选择模板和 PDF／Word／Excel；PDF 默认。生成结果是当前源单据的私有附件，完成提示提供下载链接。未保存的更改须先保存。原生 Frappe 打印菜单、附件和报价明细表的上传／下载仍按框架原样提供；没有额外增加重复导出按钮。

生成检测报告不会批准或签发报告，不写 `pdf_file`，不替换已签发附件。未签发输出明确标注草稿；已签发输出标注副本，正式签发文件仍以原报告附件为准。

## 架构与权限

`源 DocType → Service / Mapping → 文件模板 → Renderer → Frappe 私有 File`

- `document_output/registry.py`：服务端模板白名单、固定三种格式及 MIME；用户输入不能成为文件路径。
- `service.py`：读取源单据，检查 `read`、`print`；Excel 额外检查原生 `export`。应用字段级读取／脱敏权限。报告关联方案、明细方法／标准分别校验权限后读取。任何失败均不生成附件。
- `mapping/`：显式挑选输出字段；业务资料、客户要求、样品、明细、原生报价金额在此拼装。内部备注、原始附件 URL 不输出。结果为普通文本上下文。
- `renderers/`：HTML 经 Frappe 原生 `get_pdf` 生成 PDF；python-docx 展开模板行；openpyxl 填充既有 XLSX 模板并复制扩行样式、移动合并签字区及打印范围。用户字符串不会被写成 Excel 公式；PDF 对所有业务文本进行 HTML 转义。
- `templates/`：三类文档各一份 HTML／DOCX／XLSX，可在仓库修改固定模板；本轮没有在线模板设计器。

统一接口：

```python
reli_lims.document_output.api.generate_document(
    doctype="Quotation", name="SAL-QTN-2026-00001",
    template=None, output_format="pdf",
)
```

接口仅允许登录用户通过 POST 调用。返回 `file_name`、`file_url`、`file_id`、`mime_type`、`template`、`output_format`。模板名称接口同样先检查源单据权限。

## 模板来源

报价 Excel 来自用户现有 `晟楠报价单-隔振器-振动试验-报价-1.xlsx`，原文件 SHA-256：

`d13ae51edb01d04cabc0714375a0ecb5ebd271367f88fe06c262791ab6c0a1c2`

保留字体、边框、列宽、合并单元格、页设置、签字区。原模板没有显式打印范围，本轮补齐为覆盖签字区的范围。历史客户、联系人、电话、银行账号、产品和固定税率说明替换为当前单据映射或留空；不把原客户资料作为通用模板发布。合计以 ERPNext 的 `grand_total` 为准，明细金额以 ERPNext 的 `amount` 为准，另显示净额、税费和币种，不重新计算业务税费。

模板重建脚本为 `tools/build_document_templates.py`，需传入原报价文件路径。正常安装和生成不需要原文件，直接使用已打包模板。

## 依赖与部署边界

Python 依赖在 `pyproject.toml` 声明：openpyxl、python-docx；PDF 沿用 Frappe 的 PDF 环境，须具备 wkhtmltopdf 和可用中文字体。安装依赖后按正常 app 流程 migrate，`doctype_js` 将同一个脚本接到三种原生表单。本轮只在隔离验收站点验证，没有部署生产。

私有文件继续由 Frappe 控制下载；不生成公开链接，不接 Drive、ONLYOFFICE 或 Bridge。没有财务或门户写入接口。
