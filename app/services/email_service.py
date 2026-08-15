import os
import resend

from dotenv import load_dotenv


load_dotenv()


RESEND_API_KEY = os.getenv(
    "RESEND_API_KEY"
)


if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


def send_reminder_email(
    to_email: str,
    document_name: str,
    message: str,
    reminder_date: str | None = None,
    reminder_time: str | None = None,
):

    if not RESEND_API_KEY:
        return None

    date_display = (
        reminder_date
        or "Upcoming"
    )

    if reminder_time:

        date_display = (
            f"{date_display} · {reminder_time}"
        )

    params = {

        "from": (
            "Life AiOS "
            "<onboarding@resend.dev>"
        ),

        "to": [
            to_email
        ],

        "subject": (
            "🔔 Reminder from Life AiOS"
        ),

        "html": f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
Life AiOS Reminder
</title>

</head>


<body
    style="
        margin:0;
        padding:0;
        background:#f1f5f9;
        font-family:Arial, Helvetica, sans-serif;
        color:#0f172a;
    "
>


<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    style="
        background:#f1f5f9;
        padding:40px 20px;
    "
>

<tr>

<td align="center">


<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    style="
        max-width:600px;
        background:#ffffff;
        border-radius:18px;
        overflow:hidden;
        box-shadow:
            0 10px 30px
            rgba(15,23,42,0.08);
    "
>


<!-- HEADER -->

<tr>

<td
    style="
        background:
            linear-gradient(
                135deg,
                #2563eb,
                #4f46e5
            );

        padding:32px 30px;

        text-align:center;
    "
>

<div
    style="
        font-size:34px;
        margin-bottom:10px;
    "
>
🔔
</div>


<h1
    style="
        margin:0;
        color:#ffffff;
        font-size:26px;
        line-height:1.3;
    "
>
Life AiOS Reminder
</h1>


<p
    style="
        margin:8px 0 0;
        color:#dbeafe;
        font-size:14px;
    "
>
You have an upcoming reminder.
</p>


</td>

</tr>


<!-- CONTENT -->

<tr>

<td
    style="
        padding:35px 30px;
    "
>


<p
    style="
        margin:0 0 24px;
        font-size:16px;
        line-height:1.7;
        color:#334155;
    "
>
{message}
</p>


<!-- DOCUMENT CARD -->

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    style="
        background:#f8fafc;
        border:1px solid #e2e8f0;
        border-radius:12px;
        margin-bottom:24px;
    "
>

<tr>

<td
    style="
        padding:18px;
    "
>


<p
    style="
        margin:0 0 6px;
        color:#64748b;
        font-size:12px;
        text-transform:uppercase;
        letter-spacing:0.5px;
        font-weight:bold;
    "
>
Document
</p>


<p
    style="
        margin:0;
        color:#0f172a;
        font-size:15px;
        font-weight:600;
        word-break:break-word;
    "
>
📄 {document_name}
</p>


</td>

</tr>

</table>


<!-- DATE -->

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    style="
        margin-bottom:28px;
    "
>

<tr>

<td>


<p
    style="
        margin:0 0 6px;
        color:#64748b;
        font-size:12px;
        text-transform:uppercase;
        letter-spacing:0.5px;
        font-weight:bold;
    "
>
Reminder
</p>


<p
    style="
        margin:0;
        color:#334155;
        font-size:15px;
    "
>
📅 {date_display}
</p>


</td>

</tr>

</table>


<!-- BUTTON -->

<table
    cellpadding="0"
    cellspacing="0"
    style="
        margin:0 auto 10px;
    "
>

<tr>

<td
    style="
        border-radius:10px;
        background:#2563eb;
    "
>


<a
    href="http://localhost:3000"
    target="_blank"
    style="
        display:inline-block;
        padding:14px 26px;
        color:#ffffff;
        text-decoration:none;
        font-size:15px;
        font-weight:bold;
        border-radius:10px;
    "
>
Open Life AiOS →
</a>


</td>

</tr>

</table>


</td>

</tr>


<!-- FOOTER -->

<tr>

<td
    style="
        border-top:1px solid #e2e8f0;
        padding:24px 30px;
        text-align:center;
        background:#fafafa;
    "
>


<p
    style="
        margin:0 0 8px;
        color:#64748b;
        font-size:12px;
        line-height:1.6;
    "
>
This is an automated message from Life AiOS.
</p>


<p
    style="
        margin:0 0 8px;
        color:#64748b;
        font-size:12px;
        line-height:1.6;
    "
>
Please do not reply to this email.
</p>


<p
    style="
        margin:12px 0 0;
        color:#94a3b8;
        font-size:11px;
    "
>
© 2026 Life AiOS
</p>


</td>

</tr>


</table>

</td>

</tr>

</table>


</body>

</html>
        """,
    }

    try:

        response = resend.Emails.send(
            params
        )

        return response

    except Exception:

        return None