from flask import Flask, render_template, request, redirect
import os

app = Flask(__name__)

data = [
    {"id":1, "email":"test1@mail.com"},
    {"id":2, "email":"test2@mail.com"},
    {"id":3, "email":"test3@mail.com"},
]

@app.route("/", methods=["GET", "POST"])
def index():
    global data
    if request.method == "POST":
        selected = request.form.getlist("selected")
        data = [d for d in data if str(d["id"]) not in selected]
        return redirect("/")
    return render_template("index.html", data=data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))