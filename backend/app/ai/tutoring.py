"""Small, scoped hints. These are teaching prompts, never correctness evidence."""
import re


def local_hint(question: str) -> str:
    if re.search(r"连续.*紧集|紧集.*连续", question):
        return "先从紧性的开覆盖定义出发：任取像集的一个开覆盖，连续性告诉你这些开集的原像有什么性质？试着先写出原像如何覆盖原来的紧集。"
    if re.search(r"一致收敛.*连续|连续.*一致收敛", question):
        return "试着在函数值之差中加上并减去同一个 f_n 的两个函数值。你会得到三项：其中两项用一致收敛控制，另一项用什么条件控制？先写出这个三角不等式。"
    if re.search(r"特征值.*相似|相似.*特征值", question):
        return "先考虑一个重复特征值的二阶矩阵。除了特征值，还可以比较特征子空间的维数。试着构造两个特征值相同、特征子空间维数不同的矩阵。"
    if re.search(r"定积分|积分", question):
        return "先确认被积函数、积分变量和上下限。若是多项式，可以逐项找原函数；下一步需要用哪个公式把原函数与上下限联系起来？先写出原函数。"
    if re.search(r"求导|导数", question):
        return "先把表达式拆成若干项，区分常数、幂函数与复合函数。若是多项式，逐项使用幂函数求导法则；试着先处理次数最高的一项。"
    if re.search(r"归纳|1\s*\+\s*2", question):
        return "先验证命题的起始项，再写出 n=k 时的归纳假设。推到 n=k+1 时，左边比 n=k 多了哪一项？先把它单独写出来。"
    return "先列出题目已知条件和需要得到的结论，再选择一个能连接两者的定义或定理。写出你已经尝试的第一步，我可以继续针对这一步给提示。"


HINT_INSTRUCTION = (
    "你是一位数学导师。本轮是一级提示，只给一个可执行的切入点和一个引导问题。"
    "不要给最终答案、完整证明、完整反例或后续全部步骤。"
    "即使对话里已有完整答案，也不要在本轮复述它。必要条件不明确时先询问条件。"
    "不要声称提示已通过正确性验证。用中文，控制在180字以内。"
)


def complete_hint(text: str) -> bool:
    if not text or not text.strip().endswith(("。", "？", "！", ".", "?", "!", "）", ")")):
        return False
    for opening, closing in ((r"\(", r"\)"), (r"\[", r"\]")):
        if text.count(opening) != text.count(closing):
            return False
    return len(text) <= 800
