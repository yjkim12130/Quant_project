from ingest.fetch_geocode import geocode_query, parse_kakao_address, parse_kakao_keyword


def test_geocode_query_prefers_road_name():
    row = {"region_name": "강남구", "dong_name": "역삼동", "road_name": "테헤란로 123",
           "jibun": "123-45", "complex_name": "래미안역삼"}
    assert geocode_query(row, prefer="road") == "강남구 역삼동 테헤란로 123"


def test_geocode_query_falls_back_to_jibun():
    row = {"region_name": "강남구", "dong_name": "역삼동", "road_name": None,
           "jibun": "123-45", "complex_name": "래미안역삼"}
    assert geocode_query(row, prefer="jibun") == "강남구 역삼동 123-45"


def test_geocode_query_keyword_uses_complex_name():
    row = {"region_name": "강남구", "dong_name": "역삼동", "road_name": None,
           "jibun": None, "complex_name": "래미안역삼"}
    assert geocode_query(row, prefer="keyword") == "강남구 역삼동 래미안역삼"


def test_parse_kakao_address_returns_lat_lon():
    # 카카오 주소검색 API: documents[0].x=경도, documents[0].y=위도 (문자열, 최상위 필드)
    data = {"documents": [{"address": {"x": "127.123", "y": "37.456"}, "x": "127.123", "y": "37.456"}]}
    assert parse_kakao_address(data) == (37.456, 127.123)


def test_parse_kakao_address_handles_null_address_subfield():
    # 도로명에 건물번호가 없으면 address_type=ROAD, address=null, road_address만 채워짐
    # (실사용 중 발견: '영등포구 여의도동 63로' 같은 번지 없는 도로명 쿼리) —
    # 최상위 x/y는 이 경우에도 항상 채워져 있어야 한다.
    data = {"documents": [{
        "address": None,
        "address_type": "ROAD",
        "road_address": {"x": "126.9376", "y": "37.5193"},
        "x": "126.9376", "y": "37.5193",
    }]}
    assert parse_kakao_address(data) == (37.5193, 126.9376)


def test_parse_kakao_address_empty_returns_none():
    assert parse_kakao_address({"documents": []}) is None


def test_parse_kakao_keyword_returns_lat_lon():
    # 카카오 키워드검색 API: documents[0].x=경도, documents[0].y=위도 (address 중첩 없음)
    data = {"documents": [{"x": "127.111", "y": "37.222"}]}
    assert parse_kakao_keyword(data) == (37.222, 127.111)


def test_parse_kakao_keyword_empty_returns_none():
    assert parse_kakao_keyword({"documents": []}) is None
