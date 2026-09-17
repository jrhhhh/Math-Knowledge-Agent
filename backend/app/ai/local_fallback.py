"""Small deterministic answers for common theorem questions when the model is unavailable."""
import re


def local_math_answer(question: str) -> str:
    text = question.strip()
    if re.search(r"柯西中值定理", text):
        return "结论：若 f,g 在 [a,b] 上连续、在 (a,b) 内可导，且 g'(x) 不恒为 0，则存在 ξ∈(a,b) 使 (f(b)-f(a))g'(ξ)=(g(b)-g(a))f'(ξ)。证明：令 F(x)=(f(b)-f(a))g(x)-(g(b)-g(a))f(x)，由条件 F(a)=F(b)，罗尔定理给出 F'(ξ)=0，整理即得结论。"
    if re.search(r"海涅.?博雷尔|Heine.?Borel", text, re.I):
        return "定理：实数空间中的集合 K 紧，当且仅当 K 闭且有界。证明：紧集的连续坐标函数有界，且由开覆盖定义可证其补集为开集，故紧集闭且有界；反之，闭有界集包含于某个闭区间，二分覆盖或有限区间套论证表明该区间的开覆盖存在有限子覆盖，闭子集继承紧性。"
    if re.search(r"连续.*紧集|紧集.*连续|compact", text, re.I):
        return "结论：连续映射把紧集映成紧集。证明：设 f:X→Y 连续，K⊂X 紧。任取 f(K) 的开覆盖 {Vα}，则 {f⁻¹(Vα)} 是 K 的开覆盖；由紧性取有限子覆盖，其对应的有限个 Vα 覆盖 f(K)，故 f(K) 紧。"
    if re.search(r"原像.*开集|开集.*连续", text):
        return "连续性的定义正是：对陪域中的每个开集 V，原像 f⁻¹(V) 在定义域中开。因此若 f 连续，原像保持开集；反过来，对所有开集的原像都开也等价于 f 连续。"
    return ("建议按以下顺序作答：先写出定义和全部条件，再指出直接适用的定理，逐步完成推导并检查结论。"
            "当前模型暂不可用，因此无法对未覆盖的具体题目生成可靠的完整证明；请稍后重试。")
