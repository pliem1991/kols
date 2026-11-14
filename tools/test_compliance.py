"""Kiem cong tuan thu: call keo phai bi chan, bai co so lieu phai co ghi chu."""
import sys
sys.path.insert(0, r"D:\AI\XKols")
from app import brain

fail = []


def must_block(text, label):
    ok, why = brain.validate(text)
    good = not ok
    print(("  OK   " if good else "  FAIL ") + label + ("" if good else "  <-- DA CHO QUA"))
    if good:
        print(f"         ly do: {why}")
    else:
        fail.append(label)


def must_pass(text, label):
    ok, why = brain.validate(text)
    print(("  OK   " if ok else "  FAIL ") + label + ("" if ok else f"  <-- bi chan: {why}"))
    if not ok:
        fail.append(label)


print("1) CALL KEO phai bi chan (du co disclaimer)")
must_block("You should buy BTC here. Not financial advice.", "khuyen mua")
must_block("Sell the top now.", "lenh ban")
must_block("Buy $SOL before it runs.", "mua ma cu the")
must_block("Price target $92,000 by March. Not financial advice.", "gia muc tieu")
must_block("Entry at 68,400, stop-loss 66,000. NFA.", "entry + SL")
must_block("Reduce your exposure to 60%. Not financial advice.", "khuyen ty trong")
must_block("Put 20% of your portfolio in BTC. NFA.", "phan bo von")
must_block("Just DCA through it. Not financial advice.", "khuyen DCA")
must_block("3x leverage long here. NFA.", "don bay")
must_block("BTC will hit 100k this cycle. Not financial advice.", "du doan khang dinh")
must_block("This setup is risk-free. NFA.", "hua hen")
must_block("Going all in on this one.", "vao het")
must_block("Last chance to get in under 70k. NFA.", "giuc xuong tien")
must_block("Re-enter on a reclaim of the 200 SMA. Not financial advice.", "diem vao lai")

print("\n2) Bai co so lieu ma THIEU ghi chu -> chan")
must_block("BTC closed at $68,714. RSI 25.9, lowest in 30 days.", "so lieu khong ghi chu")
must_block("Model rated BTC underweight on 13 Nov.", "nhan xep loai khong ghi chu")
must_block("Stablecoin outflows hit 14.2B, down 9.5% in 8 days.", "phan tram khong ghi chu")

print("\n3) Bai hop le -> phai cho qua")
must_pass("BTC closed at $68,714 in the 13 Nov run. RSI 25.9.\n\n"
          "Not financial advice.", "ta so lieu + ghi chu")
must_pass("The model classified BTC as underweight on 13 Nov.\n\n"
          "It has been wrong at this exact reading twice.\n\n"
          "Not financial advice.", "ta nhan xep loai + ghi chu")
# Chu du an chot 14/11: ghi du chu, khong dung "NFA".
must_block("Model output, 13 Nov: underweight. NFA.", "viet tat NFA")
must_block("BTC closed at $68,714 in the 13 Nov run.\n\nNFA", "NFA khong dau cham")
must_pass("Reading forty sources to conclude 'unclear' is still a result.\n\n"
          "An expensive one.", "quan sat chung, khong cham thi truong")
must_pass("Liquidation cascades feed themselves: forced selling moves price, "
          "which forces the next tier out.", "giai thich co che")
# Sua 14/11 lan hai: noi dung meta bi cam han, truoc kia hai mau nay duoc cho qua.
must_block("Our bull agent and bear agent disagreed for nine turns.\n\n"
           "Then both were wrong.", "viet ve agent cua minh")
must_block("Prompt design note: we stopped letting the risk agent see the "
           "price. Its calls got better.", "viet ve prompt design")

print("\n4) Thread: ghi chu phai o bai cuoi")
good = ["Model output for BTC, 13 Nov run: underweight. Close $68,714.",
        "Bearish: below the 200 SMA at $73,068.",
        "Bullish: RSI 25.9, under the lower band.",
        "AI-generated analysis from a multi-agent pipeline.\n\nNot financial advice."]
ok, why = brain.validate_thread(good)
print(("  OK   " if ok else "  FAIL ") + "thread dung" + ("" if ok else f"  <-- {why}"))
if not ok:
    fail.append("thread dung")

no_disc = good[:-1] + ["That is the whole run."]
ok, why = brain.validate_thread(no_disc)
print(("  OK   " if not ok else "  FAIL ") + "thread thieu ghi chu bi chan")
if not ok:
    print(f"         ly do: {why}")
else:
    fail.append("thread thieu ghi chu")

wrong_place = ["Not financial advice. Model output: underweight.",
               "Bearish: below the 200 SMA.", "That is the run."]
ok, why = brain.validate_thread(wrong_place)
print(("  OK   " if not ok else "  FAIL ") + "ghi chu khong o bai cuoi bi chan")
if not ok:
    print(f"         ly do: {why}")
else:
    fail.append("ghi chu sai cho")

with_call = good[:-1] + ["Re-enter on a 200 SMA reclaim.\n\nNot financial advice."]
ok, why = brain.validate_thread(with_call)
print(("  OK   " if not ok else "  FAIL ") + "thread co call keo bi chan")
if not ok:
    print(f"         ly do: {why}")
else:
    fail.append("thread co call keo")

print()
if fail:
    print(f"THAT BAI {len(fail)}: " + ", ".join(fail))
    sys.exit(1)
print("TAT CA DAT")
