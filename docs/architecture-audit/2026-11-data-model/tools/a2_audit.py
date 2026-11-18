import frappe, json, csv, statistics, re, os
frappe.init(site="carl", sites_path="/home/frappe/pilot/benches/dev-bench/sites"); frappe.connect()
OUT="/tmp/auditout"; os.makedirs(OUT, exist_ok=True)
R={}

caps=frappe.db.sql("""select name, laboratory, test_project, test_object, test_standard,
 clause, limitation, product_scope, capability_scope, condition_schema, published, status, demo_only
 from `tabLaboratory Capability`""",as_dict=True)
R["cap_total"]=len(caps)
R["caps_no_project"]=sum(1 for c in caps if not c.test_project)
R["caps_no_lab"]=sum(1 for c in caps if not c.laboratory)
R["caps_published"]=sum(1 for c in caps if c.published)
R["labs"]=frappe.db.sql("select name from `tabLaboratory Profile`",pluck=True)

projs=frappe.db.sql("select name, project_name, normalized_name, classification_status, condition_template from `tabTest Project`",as_dict=True)
R["proj_total"]=len(projs)
R["proj_no_cap"]=sorted(p["name"] for p in projs if not any(c.test_project==p["name"] for c in caps))

# per project aggregation
by_p={}
for c in caps:
    by_p.setdefault(c.test_project,[]).append(c)
matrix=[]; child_mismatch=[]
for p in projs:
    cs=by_p.get(p["name"],[])
    labs=sorted({c.laboratory for c in cs if c.laboratory})
    stds=sorted({c.test_standard for c in cs if c.test_standard})
    objs=sorted({c.test_object for c in cs if c.test_object})
    ch_std=set(frappe.db.sql("select test_standard from `tabTest Project Standard` where parent=%s and ifnull(test_standard,'')!=''",p["name"],pluck=True))
    ch_obj=set(frappe.db.sql("select test_object from `tabTest Project Object` where parent=%s and ifnull(test_object,'')!=''",p["name"],pluck=True))
    per_lab={}
    for c in cs:
        d=per_lab.setdefault(c.laboratory or "(none)",{"std":set(),"obj":set(),"n":0})
        d["n"]+=1
        if c.test_standard: d["std"].add(c.test_standard)
        if c.test_object: d["obj"].add(c.test_object)
    single_lab_cover=any(set(stds)<=per_lab[l]["std"] for l in per_lab) if per_lab else False
    matrix.append({
      "project":p["name"],"project_name":p["project_name"],"classification":p["classification_status"],
      "caps":len(cs),"labs":len(labs),"lab_names":"|".join(labs),
      "std_n":len(stds),"obj_n":len(objs),"child_std_n":len(ch_std),"child_obj_n":len(ch_obj),
      "std_missing_in_child":len(set(stds)-ch_std),"std_extra_in_child":len(ch_std-set(stds)),
      "obj_missing_in_child":len(set(objs)-ch_obj),"obj_extra_in_child":len(ch_obj-set(objs)),
      "multi_lab":len(labs)>1,"single_lab_can_cover_all":single_lab_cover,
      "condition_template":bool(p["condition_template"])
    })
    if len(labs)>1 and not single_lab_cover:
        child_mismatch.append({**matrix[-1], "per_lab":{l:{"caps":v["n"],"std":len(v["std"]),"obj":len(v["obj"])} for l,v in per_lab.items()}})

with open(f"{OUT}/coverage_matrix.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(matrix[0].keys())); w.writeheader(); w.writerows(matrix)
R["matrix_rows"]=len(matrix)
R["matrix_multi_lab_projects"]=sum(1 for m in matrix if m["multi_lab"])
R["matrix_cross_lab_uncoverable"]=len(child_mismatch)
R["cross_lab_detail"]=child_mismatch[:40]
R["matrix_child_std_drift"]=sum(1 for m in matrix if m["std_missing_in_child"] or m["std_extra_in_child"])
R["matrix_child_obj_drift"]=sum(1 for m in matrix if m["obj_missing_in_child"] or m["obj_extra_in_child"])
cap_dist=[m["caps"] for m in matrix if m["caps"]>0]
R["caps_per_project"]={"min":min(cap_dist),"median":statistics.median(cap_dist),"max":max(cap_dist),"mean":round(statistics.mean(cap_dist),1)}
R["top_projects"]=sorted([m for m in matrix if m["caps"]],key=lambda m:-m["caps"])[:15]

# within-project variance
var=[]
for p in projs:
    cs=by_p.get(p["name"],[])
    if len(cs)<2: continue
    d={
     "project":p["name"],"project_name":p["project_name"],"caps":len(cs),
     "std_variants":len({c.test_standard for c in cs if c.test_standard}),
     "obj_variants":len({c.test_object for c in cs if c.test_object}),
     "limits_variants":len({(c.limitation or "").strip() for c in cs}),
     "schema_variants":len({(c.condition_schema or "").strip() for c in cs}),
     "scope_variants":len({(c.capability_scope or "").strip() for c in cs}),
     "clause_variants":len({(c.clause or "").strip() for c in cs}),
    }
    d["needs_spec"]= d["limits_variants"]>1 or d["schema_variants"]>1 or d["scope_variants"]>1
    var.append(d)
with open(f"{OUT}/project_variance.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(var[0].keys())); w.writeheader(); w.writerows(var)
R["variance_projects"]=len(var)
R["variance_needs_spec"]=sum(1 for v in var if v["needs_spec"])
R["variance_std_gt1"]=sum(1 for v in var if v["std_variants"]>1)
R["variance_obj_gt1"]=sum(1 for v in var if v["obj_variants"]>1)
R["variance_schema_gt1"]=sum(1 for v in var if v["schema_variants"]>1)
R["variance_limits_gt1"]=sum(1 for v in var if v["limits_variants"]>1)

# quotation overwrite audit
qrows=frappe.db.sql("""select qi.name qi, qi.parent, qi.idx, qi.custom_reli_capability cap, qi.custom_reli_test_project rp,
 qi.custom_reli_test_object ro, qi.custom_reli_test_standard rs, qi.custom_reli_configuration cfg, q.docstatus, q.status
 from `tabQuotation Item` qi join `tabQuotation` q on q.name=qi.parent
 where ifnull(qi.custom_reli_capability,'')!=''""",as_dict=True)
capmap={c.name:c for c in caps}
drift=[]
for r in qrows:
    c=capmap.get(r["cap"])
    if not c: drift.append({"qi":r["qi"],"parent":r["parent"],"reason":"capability 不存在（已删除）","docstatus":r["docstatus"]}); continue
    bad=[k for k,f in (("project","rp"),("object","ro"),("standard","rs")) if (r[f] or "")!=(c[{"project":"test_project","object":"test_object","standard":"test_standard"}[k]] or "")]
    if bad:
        drift.append({"qi":r["qi"],"parent":r["parent"],"idx":r["idx"],"docstatus":r["docstatus"],
          "diff_fields":"|".join(bad),
          "quoted":{k:r[f] for k,f in (("project","rp"),("object","ro"),("standard","rs"))},
          "live":{k:c[{"project":"test_project","object":"test_object","standard":"test_standard"}[k]] for k in ("project","object","standard")}})
with open(f"{OUT}/quotation_drift.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["qi","parent","idx","docstatus","diff_fields","quoted","live","reason"]); w.writeheader()
    for d in drift: w.writerow({k:d.get(k,"") for k in w.fieldnames})
R["quot_rows_with_cap"]=len(qrows)
R["quot_rows_no_cfg"]=sum(1 for r in qrows if not r["cfg"])
R["quot_drift_rows"]=len(drift)
R["quot_drift_submitted"]=sum(1 for d in drift if d.get("docstatus")==1)
R["quot_drift_by_field"]={}
for d in drift:
    for k in (d.get("diff_fields") or "missing_capability").split("|"):
        R["quot_drift_by_field"][k]=R["quot_drift_by_field"].get(k,0)+1
R["quot_drift_samples"]=drift[:25]
R["quot_total"]=frappe.db.sql("select count(*) from tabQuotation")[0][0]
R["quot_items_total"]=frappe.db.sql("select count(*) from `tabQuotation Item`")[0][0]

# item<->project consistency
items=frappe.db.sql("""select name, item_code, custom_reli_test_project tp, custom_reli_service_capability sc,
 standard_rate, item_name from `tabItem` where ifnull(custom_reli_business_type,'')='检测服务'""",as_dict=True)
R["svc_items"]=len(items)
imis=[]
for it in items:
    c=capmap.get(it["sc"])
    if c and (c.test_project or "")!=(it["tp"] or ""):
        imis.append({"item":it["name"],"item_project":it["tp"],"cap":it["sc"],"cap_project":c.test_project})
R["item_cap_project_mismatch"]=imis
R["svc_items_without_cap"]=[i["name"] for i in items if not i["sc"]]

# 高温试验 / 温度循环 案例
kw=["高温","温度循环","低温","湿热","恒温恒湿"]
cases={}
for k in kw:
    hits=[m for m in matrix if k in (m["project_name"] or "")]
    cases[k]=sorted([{"project":m["project"],"name":m["project_name"],"caps":m["caps"],"labs":m["lab_names"],"std_n":m["std_n"],"obj_n":m["obj_n"]} for m in hits],key=lambda x:-x["caps"])[:6]
R["cases"]=cases

# detail for top 高温 project + top 温度循环 project
def detail(pname):
    cs=by_p.get(pname,[])
    qi=frappe.db.sql("""select qi.parent, qi.custom_reli_test_standard s, qi.custom_reli_test_object o, qi.rate, qi.custom_reli_configuration cfg
      from `tabQuotation Item` qi where qi.custom_reli_test_project=%s""",pname,as_dict=True)
    it=[i for i in items if i["tp"]==pname]
    return {"project":pname,"caps":[{ "cap":c.name,"lab":c.laboratory,"std":c.test_standard,"obj":c.test_object,"clause":c.clause,"limitation":c.limitation,"scope":c.capability_scope,"schema":bool(c.condition_schema),"published":c.published} for c in cs],
      "quotation_lines":{"n":len(qi),"distinct_rates":len({q.rate for q in qi}),"distinct_std":len({q.s for q in qi}),"distinct_obj":len({q.o for q in qi}),"sample":[{"parent":q.parent,"std":q.s,"obj":q.o,"rate":q.rate,"has_cfg":bool(q.cfg)} for q in qi[:20]]},
      "items":[{"item":i["name"],"rate":i["standard_rate"]} for i in it]}
R["case_detail"]={k:detail(v[0]["project"]) for k,v in cases.items() if v}
for k,v in R["case_detail"].items():
    if len(v["caps"])>8: v["caps"]=v["caps"][:8]

json.dump(R,open(f"{OUT}/a2_result.json","w"),ensure_ascii=False,default=str,indent=1)
print(json.dumps({k:v for k,v in R.items() if k not in("cross_lab_detail","top_projects","quot_drift_samples","case_detail","cases","item_cap_project_mismatch")},ensure_ascii=False,indent=1))
