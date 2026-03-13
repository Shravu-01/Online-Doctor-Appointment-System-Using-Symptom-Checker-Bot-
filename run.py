from proj import create_app, db


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()   # ensures tables are created
    app.run(debug=True)


@app.route("/test-direct")
def test_direct():
    return "DIRECT ROUTE WORKS"

