# -*- coding: utf-8 -*-
"""
ApiExecutor._modify_api_code 의 stock_name 패스스루 버그 회귀 테스트.

버그: _process_stock_name 이 종목명을 해소하면서 원본 stock_name 키를 제거하지 않고
_resolved_stock_code/_original_search_value/pdno 메타 키를 추가하는데,
_modify_api_code 가 이 키들을 그대로 함수 kwargs 로 넘겨버려
`TypeError: inquire_price() got an unexpected keyword argument 'stock_name'` 이 발생한다.

기대 동작:
1. 함수 시그니처에 없는 키(stock_name, _resolved_stock_code, _original_search_value)는 호출에서 제거된다.
2. 해소된 종목코드는 함수가 실제로 받는 종목코드 파라미터(fid_input_iscd)에 매핑된다.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tools.base import ApiExecutor  # noqa: E402


# 실제 다운로드되는 examples_llm/domestic_stock/inquire_price 구조를 모사.
# (함수 추출 정규식이 본문의 `if res.isOK():` 의 `):` 에 의존하므로 본문을 포함한다.)
SAMPLE_FUNC = '''
import pandas as pd
import kis_auth as ka

API_URL = "/uapi/domestic-stock/v1/quotations/inquire-price"

def inquire_price(
    env_dv: str,                  # [필수] 실전모의구분 (ex. real:실전, demo:모의)
    fid_cond_mrkt_div_code: str,  # [필수] 조건 시장 분류 코드 (ex. J:KRX)
    fid_input_iscd: str           # [필수] 입력 종목코드 (ex. 005930)
) -> pd.DataFrame:
    tr_id = "FHKST01010100"
    params = {
        "FID_COND_MRKT_DIV_CODE": fid_cond_mrkt_div_code,
        "FID_INPUT_ISCD": fid_input_iscd
    }
    res = ka._url_fetch(API_URL, tr_id, "", params)
    if res.isOK():
        return pd.DataFrame(res.getBody().output, index=[0])
    else:
        return pd.DataFrame()
'''


def _generate_call_code(params):
    """샘플 함수 소스에 _modify_api_code 를 적용하고 생성된 전체 코드를 반환."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_FUNC)
        path = f.name
    try:
        ApiExecutor._modify_api_code(path, dict(params), "domestic_stock")
        with open(path, encoding="utf-8") as f:
            return f.read()
    finally:
        os.unlink(path)


def _call_line(code):
    for line in code.splitlines():
        if "result = inquire_price(" in line:
            return line
    raise AssertionError("생성된 코드에서 호출 라인을 찾지 못함:\n" + code)


def test_stock_name_meta_keys_stripped_and_code_mapped():
    # _process_stock_name 통과 후의 params 모사 (stock_name='삼성전자' 호출)
    params = {
        "stock_name": "삼성전자",
        "env_dv": "real",
        "fid_cond_mrkt_div_code": "J",
        "pdno": "005930",
        "_original_search_value": "삼성전자",
        "_resolved_stock_code": "005930",
    }
    code = _generate_call_code(params)
    call = _call_line(code)

    # 1) 함수가 받지 않는 메타 키가 호출에 남아 있으면 안 된다.
    assert "stock_name=" not in call, f"stock_name 이 호출에 남음: {call}"
    assert "_resolved_stock_code=" not in call, f"_resolved_stock_code 가 호출에 남음: {call}"
    assert "_original_search_value=" not in call, f"_original_search_value 가 호출에 남음: {call}"
    assert "pdno=" not in call, f"pdno(미지원 파라미터)가 호출에 남음: {call}"

    # 2) 해소된 종목코드는 fid_input_iscd 로 매핑되어야 한다.
    assert "fid_input_iscd='005930'" in call, f"fid_input_iscd 매핑 누락: {call}"
    assert "env_dv='real'" in call
    assert "fid_cond_mrkt_div_code='J'" in call


def _generate_call_for(func_src, params, api_type):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(func_src)
        path = f.name
    try:
        ApiExecutor._modify_api_code(path, dict(params), api_type)
        with open(path, encoding="utf-8") as f:
            return f.read()
    finally:
        os.unlink(path)


ORDER_FUNC = '''
import pandas as pd
import kis_auth as ka

def order(
    env_dv: str,
    ord_dv: str,
    cano: str,
    acnt_prdt_cd: str,
    pdno: str,
    ord_qty: str,
    ord_unpr: str
) -> pd.DataFrame:
    res = ka._url_fetch("/x", "TTTC0802U", "", {})
    if res.isOK():
        return pd.DataFrame()
    else:
        return pd.DataFrame()
'''

OVERSEAS_FUT_FUNC = '''
import pandas as pd
import kis_auth as ka

def inquire_price(
    srs_cd: str,
    tr_cont: str = "",
) -> pd.DataFrame:
    res = ka._url_fetch("/y", "HHDFC55010000", "", {})
    if res.isOK():
        return pd.DataFrame()
    else:
        return pd.DataFrame()
'''


def test_order_api_keeps_pdno_when_function_accepts_it():
    # 주문 API: 함수가 pdno 를 직접 받는다 → pdno(해소된 코드) 유지, 메타키 제거
    params = {
        "stock_name": "삼성전자",
        "env_dv": "real",
        "ord_dv": "buy",
        "pdno": "005930",
        "ord_qty": "1",
        "ord_unpr": "0",
        "_original_search_value": "삼성전자",
        "_resolved_stock_code": "005930",
    }
    code = _generate_call_for(ORDER_FUNC, params, "domestic_stock")
    call = next(l for l in code.splitlines() if "result = order(" in l)
    assert "stock_name=" not in call
    assert "_resolved_stock_code=" not in call
    assert "pdno='005930'" in call, f"pdno 유지 실패: {call}"
    # cano/acnt_prdt_cd 는 계좌 자동매핑으로 ka._TRENV 값이 들어가야 한다
    assert "cano=ka._TRENV.my_acct" in call


def test_resolved_code_maps_to_srs_cd_for_overseas_future():
    # 해외선물: 함수가 srs_cd 를 받는다 → 해소된 코드가 srs_cd 로 매핑, pdno 제거
    params = {
        "stock_name": "삼성전자",
        "pdno": "005930",
        "_original_search_value": "삼성전자",
        "_resolved_stock_code": "005930",
    }
    code = _generate_call_for(OVERSEAS_FUT_FUNC, params, "overseas_futureoption")
    call = next(l for l in code.splitlines() if "result = inquire_price(" in l)
    assert "stock_name=" not in call
    assert "pdno=" not in call, f"pdno 미제거: {call}"
    assert "srs_cd='005930'" in call, f"srs_cd 매핑 실패: {call}"


PRDT_PDNO_FUNC = '''
import pandas as pd
import kis_auth as ka

def inquire_something(
    env_dv: str,
    prdt_pdno: str
) -> pd.DataFrame:
    res = ka._url_fetch("/z", "TTTC0000", "", {})
    if res.isOK():
        return pd.DataFrame()
    else:
        return pd.DataFrame()
'''


def test_substring_false_positive_pdno_not_leaked():
    # 함수가 'prdt_pdno' 만 받고 bare 'pdno' 는 받지 않는다.
    # substring 매칭이면 'pdno' in "...prdt_pdno..." → True 라 pdno 가 호출에 새어
    # `TypeError: unexpected keyword argument 'pdno'` 가 재발한다. 정확한 이름 매칭이어야 한다.
    params = {
        "stock_name": "삼성전자",
        "env_dv": "real",
        "pdno": "005930",
        "_original_search_value": "삼성전자",
        "_resolved_stock_code": "005930",
    }
    code = _generate_call_for(PRDT_PDNO_FUNC, params, "domestic_stock")
    call = next(l for l in code.splitlines() if "result = inquire_something(" in l)
    assert "stock_name=" not in call
    # 함수가 받지 않는 bare pdno 는 호출에 남으면 안 된다 (오탐 방지의 핵심)
    assert "pdno='005930'" not in call, f"pdno 가 호출에 새어나감(오탐): {call}"
    # prdt_pdno 는 우선순위 목록에 없으므로 매핑되지 않고, 메타키 제거로 TypeError 만 사라진다
    assert "prdt_pdno=" not in call


def test_no_stock_name_call_unaffected():
    # stock_name 없이 직접 종목코드를 준 기존 정상 호출은 그대로 동작해야 한다
    params = {
        "env_dv": "real",
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": "005930",
    }
    code = _generate_call_code(params)
    call = _call_line(code)
    assert "fid_input_iscd='005930'" in call
    assert "env_dv='real'" in call
    assert "fid_cond_mrkt_div_code='J'" in call


if __name__ == "__main__":
    test_stock_name_meta_keys_stripped_and_code_mapped()
    test_order_api_keeps_pdno_when_function_accepts_it()
    test_resolved_code_maps_to_srs_cd_for_overseas_future()
    test_substring_false_positive_pdno_not_leaked()
    test_no_stock_name_call_unaffected()
    print("PASS")
