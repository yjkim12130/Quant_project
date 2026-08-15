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
    # 카카오 주소검색 API: address.x=경도, address.y=위도 (문자열)
    data = {"documents": [{"address": {"x": "127.123", "y": "37.456"}}]}
    assert parse_kakao_address(data) == (37.456, 127.123)


def test_parse_kakao_address_empty_returns_none():
    assert parse_kakao_address({"documents": []}) is None


def test_parse_kakao_keyword_returns_lat_lon():
    # 카카오 키워드검색 API: documents[0].x=경도, documents[0].y=위도 (address 중첩 없음)
    data = {"documents": [{"x": "127.111", "y": "37.222"}]}
    assert parse_kakao_keyword(data) == (37.222, 127.111)


def test_parse_kakao_keyword_empty_returns_none():
    assert parse_kakao_keyword({"documents": []}) is None
