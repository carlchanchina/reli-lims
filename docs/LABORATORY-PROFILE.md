# Mercur 实验室商家资料

`Laboratory Profile` 以 Mercur seller ID 为唯一键，保存商家提交的 `draft_json` 与审核后的 `published_json`。商家再次提交不会覆盖已公开版本。可填写简介、地区、响应时间、检测能力、设备、标准、行业案例、证书名称/范围/有效期；这些是商家申报资料，不自动证明 CNAS/CMA 资质。

Mercur Vendor 服务端调用 `get_vendor_profile` 与 `submit_vendor_profile`，使用专用 Frappe API 用户的 `Mercur Integration` 角色；浏览器不能直连。`expected_revision` 防止旧页面覆盖新草稿。`Lab Reviewer` 在 ERPNext Desk 的 Laboratory Profile 页面查看申报资料并选择“通过审核”或“退回修改”；审核接口核对版本，只有通过时复制到公开快照。ReliLab Core 的公开目录使用独立的 `Laboratory Directory Reader` 角色服务凭证读取 `list_published_profiles`，只返回审核过的快照，不能提交商家草稿。

安装：更新应用后，在目标站点运行 `bench --site <site> migrate`，检查 Role fixture 与 DocType。为 Mercur 和 ReliLab Core 分别配置最小权限 API 用户；不要把 API secret 放入浏览器或仓库。上线前在独立测试站点验证两个同名 seller ID 的隔离、重复提交、退回、重新提交、审核后旧版本保持公开，以及未经审核资料不可见。首个目标 seller ID 为 `sel_01M4NQTT8KMTVHR8HRM9RFTCA0`（旭博检测／人民币）；不自动绑定另一账号。
