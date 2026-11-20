"""dashkit — khung màn hình theo dõi chạy local, dùng chung cho nhiều app.

Tách ra khỏi app/web.py ngày 20/11 để project Facebook dùng lại được. Trong
này KHÔNG có một dòng nào biết X hay Facebook là gì: chỉ có server, cổng mật
khẩu, CSS và phần JS khung (đổi mục, tự nạp lại, biểu đồ cột, chép draft).

Cách dùng, xem dashkit/README.md. Bộ xương:

    import dashkit
    dash = dashkit.Dash(
        name="FBKols", icon="F",
        nav=[dashkit.Nav("overview", "Tổng quan"), ...],
        app_js=MY_JS,            # các hàm v_<key>(d) và head(d)
        state=lambda: {...},     # trả JSON cho /api/state
        gate=dashkit.Gate(env_file=..., token_key=..., pass_key=...,
                          now=..., cookie="fb"),   # cookie PHẢI khác app khác
        port=8788,
    )
    print(dashkit.serve(dash))
"""
from .gate import Gate
from .page import CSS, Nav, build, login, nav_html
from .server import Dash, Server, handler_for, serve, shared_links

__all__ = ["CSS", "Dash", "Gate", "Nav", "Server", "build", "handler_for",
           "login", "nav_html", "serve", "shared_links"]
