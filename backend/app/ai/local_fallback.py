"""可扩展的确定性数学回答模板；模型不可用时提供可靠的基础答案。"""
import re
from datetime import datetime, timezone

LOCAL_TEMPLATES = (
    ("cauchy_mean_value", re.compile(r"柯西中值定理"), "结论：若 f,g 在 [a,b] 上连续、在 (a,b) 内可导，且 g'(x) 不恒为 0，则存在 ξ∈(a,b) 使 (f(b)-f(a))g'(ξ)=(g(b)-g(a))f'(ξ)。证明：令 F(x)=(f(b)-f(a))g(x)-(g(b)-g(a))f(x)，由条件 F(a)=F(b)，罗尔定理给出 F'(ξ)=0，整理即得结论。"),
    ("heine_borel", re.compile(r"海涅.?博雷尔|Heine.?Borel", re.I), "定理：实数空间中的集合 K 紧，当且仅当 K 闭且有界。证明：紧集的连续坐标函数有界，且由开覆盖定义可证其补集为开集，故紧集闭且有界；反之，闭有界集包含于某个闭区间，二分覆盖或有限区间套论证表明该区间的开覆盖存在有限子覆盖，闭子集继承紧性。"),
    ("continuous_image_compact", re.compile(r"连续.*紧集|紧集.*连续|compact", re.I), "结论：连续映射把紧集映成紧集。证明：设 f:X→Y 连续，K⊂X 紧。任取 f(K) 的开覆盖 {Vα}，则 {f⁻¹(Vα)} 是 K 的开覆盖；由紧性取有限子覆盖，其对应的有限个 Vα 覆盖 f(K)，故 f(K) 紧。"),
    ("preimage_open", re.compile(r"原像.*开集|开集.*连续"), "连续性的定义正是：对陪域中的每个开集 V，原像 f⁻¹(V) 在定义域中开。因此若 f 连续，原像保持开集；反过来，对所有开集的原像都开也等价于 f 连续。"),
    ("continuous_bounded_compact", re.compile(r"连续函数.*有界|紧集上有界|有界.*连续"), "结论：连续函数在紧集 K 上有界。证明：f(K) 是紧集，而实数中的紧集闭且有界；因此存在 M>0，使对所有 x∈K 都有 |f(x)|≤M。"),
    ("continuous_preimage_closed", re.compile(r"原像.*闭集|闭集.*原像"), "结论：连续映射的闭集原像是闭集。证明：设 C 为陪域中的闭集，则 Y\\C 开；连续性给出 f⁻¹(Y\\C) 开，而 f⁻¹(Y\\C)=X\\f⁻¹(C)，故 f⁻¹(C) 闭。"),
    ("extreme_value", re.compile(r"最大值.*最小值|最值定理|取得最大值"), "极值定理：连续函数在非空紧集上取得最大值和最小值。证明：连续像 f(K) 紧，实数中的紧集有界且闭；设上确界为 M，则 M∈f(K)，故存在 x_max∈K 使 f(x_max)=M；最小值同理。"),
    ("intermediate_value", re.compile(r"介值定理|中间值定理|零点定理"), "介值定理：若 f 在 [a,b] 上连续，且 y 介于 f(a)、f(b) 之间，则存在 c∈[a,b] 使 f(c)=y。证明：考虑集合 {x∈[a,b]:f(x)≤y} 的上确界 c，利用连续性排除 f(c)<y 与 f(c)>y，遂得 f(c)=y。"),
)


def match_local_template(question: str, db=None):
    text = question.strip()
    if db is not None:
        from app.models.local_template import LocalTemplate
        for item in db.query(LocalTemplate).filter(LocalTemplate.enabled.is_(True), LocalTemplate.review_status == "approved").order_by(LocalTemplate.id.asc()).all():
            try:
                if re.search(item.pattern, text, re.I):
                    item.hit_count += 1
                    item.last_hit_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.commit()
                    return {"id": item.template_id, "answer": item.answer}
            except re.error:
                continue
    for template_id, pattern, answer in LOCAL_TEMPLATES:
        if pattern.search(text):
            return {"id": template_id, "answer": answer}
    return None


def local_math_answer(question: str, db=None) -> str:
    matched = match_local_template(question, db)
    if matched:
        return matched["answer"]
    return ("建议按以下顺序作答：先写出定义和全部条件，再指出直接适用的定理，逐步完成推导并检查结论。"
            "当前模型暂不可用，因此无法对未覆盖的具体题目生成可靠的完整证明；请稍后重试。")
