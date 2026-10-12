import datetime
import hashlib
import mimetypes
import os
import reflex as rx
from sqlalchemy import Column, LargeBinary
from sqlmodel import Field, select
#settings
blocked_types = [".exe", ".bat", ".cmd", ".msi", ".ps1", ".sh", ".js"]
max_size_mb = 10
max_files = 10
#dropdown values
this_year = datetime.date.today().year
days = [str(d) for d in range(1, 32)]
months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
years = [str(y) for y in range(this_year, this_year - 100, -1)]
#tables
class Registration(rx.Model, table=True):
    full_name: str
    email: str = Field(unique=True)
    phone: str = Field(unique=True)
    dob: str
    gender: str
    password: str
class Media(rx.Model, table=True):
    registration_id: int = Field(foreign_key="registration.id")
    media_type: str
    file_name: str
    size_kb: int
    file_data: bytes = Field(sa_column=Column(LargeBinary))
#email check
def check_email(email):
    if len(email) > 254 or " " in email:
        return False 
    if email.count("@") != 1:
        return False
    name, domain = email.split("@") 
    if name == "" or domain == "": 
        return False
    if "." not in domain or domain.startswith(".") or domain.endswith(".") or ".." in domain:
        return False 
    ending = domain.split(".")[-1] 
    return ending.isalpha() and len(ending) >= 2 
# logic
class State(rx.State):
    show_popup: bool = False
    popup_title: str = ""
    popup_message: str = ""
    new_user_id: int = 0
    user_name: str = ""
    pending_names: list[str] = []
    upload_log: list[str] = []
    _pending: list = []
    editing: bool = False
    changing_password: bool = False
    profile_name: str = ""
    profile_email: str = ""
    profile_phone: str = ""
    profile_day: str = ""
    profile_month: str = ""
    profile_year: str = ""
    profile_gender: str = ""
    profile_files: list[dict[str, str]] = []
    def open_popup(self, title, message):
        self.popup_title = title
        self.popup_message = message
        self.show_popup = True
    def close_popup(self):
        self.show_popup = False
    def reset_all(self):
        self.new_user_id = 0
        self.user_name = ""
        self.editing = False
        self.changing_password = False
        self._pending = []
        self.pending_names = []
        self.upload_log = []
        self.profile_files = []
    def check_dob(self, day, month, year):
        try:
            datetime.date(int(year), months.index(month) + 1, int(day))
            return True
        except ValueError:
            return False

    def register(self, form_data: dict):
        full_name = form_data["full_name"].strip()
        email = form_data["email"].strip().lower()
        phone = form_data["phone"].strip()
        gender = form_data["gender"]
        password = form_data["password"]
        confirm = form_data["confirm_password"]
        day = form_data["dob_day"]
        month = form_data["dob_month"]
        year = form_data["dob_year"]
        dob = day + "/" + month + "/" + year
        if not check_email(email):
            self.open_popup("Error", "Please enter a valid email.")
            return
        if not phone.isdigit() or len(phone) != 10:
            self.open_popup("Error", "Phone number must be 10 digits.")
            return
        if not self.check_dob(day, month, year):
            self.open_popup("Error", "Please select a valid date of birth.")
            return
        if password != confirm:
            self.open_popup("Error", "Passwords do not match.")
            return
        if len(password) < 6:
            self.open_popup("Error", "Password must be at least 6 characters.")
            return
        with rx.session() as session:
            if session.exec(select(Registration).where(Registration.email == email)).first():
                self.open_popup("Already Registered", "This user is already registered.")
                return
            if session.exec(select(Registration).where(Registration.phone == phone)).first():
                self.open_popup("Already Registered", "This phone number is already registered.")
                return
            hashed = hashlib.sha256(password.encode()).hexdigest()
            new_user = Registration(full_name=full_name, email=email, phone=phone, dob=dob, gender=gender, password=hashed)
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            self.new_user_id = new_user.id
        self.user_name = full_name.split(" ")[0]
        self._pending = []
        self.pending_names = []
        self.upload_log = []
        return rx.redirect("/upload")
  
    def login(self, form_data: dict):
        email = form_data["email"].strip().lower()
        hashed = hashlib.sha256(form_data["password"].encode()).hexdigest() #64 hexadecimal letters
        with rx.session() as session:
            user = session.exec(select(Registration).where(Registration.email == email)).first()
        if user is None or user.password != hashed:
            self.open_popup("Sign in failed", "Incorrect email or password.")
            return
        self.new_user_id = user.id
        self.user_name = user.full_name.split(" ")[0]
        return rx.redirect("/profile")
    def logout(self):
        self.reset_all()
        return rx.redirect("/login")

    def check_upload_page(self):
        if self.new_user_id == 0:
            return rx.redirect("/login")
    async def add_files(self, files: list[rx.UploadFile]):
        if self.new_user_id == 0:
            self.open_popup("Error", "Please register or sign in first.")
            return
        for file in files:
            name = file.filename
            extension = os.path.splitext(name)[1].lower()
            if extension in blocked_types:
                self.upload_log.append(name + " - skipped")
                continue
            media_type = (mimetypes.guess_type(name)[0] or "other/unknown").split("/")[0]
            if media_type not in ["image", "audio", "video"]:
                media_type = "document"
            data = await file.read()
            if len(data) > max_size_mb * 1024 * 1024:
                self.upload_log.append(name + " - skipped (over " + str(max_size_mb) + " MB)")
                continue
            self._pending = self._pending + [(name, media_type, data)]
            self.pending_names.append(name + " (" + media_type + ", " + str(len(data) // 1024) + " KB)")
        yield rx.clear_selected_files("media_upload")
    def clear_files(self):
        self._pending = []
        self.pending_names = []
        self.upload_log = []
    def submit_files(self):
        if len(self._pending) == 0:
            self.open_popup("Error", "Please add at least one file first.")
            return
        with rx.session() as session:
            for item in self._pending:
                session.add(Media(registration_id=self.new_user_id, media_type=item[1], file_name=item[0], size_kb=len(item[2]) // 1024, file_data=item[2]))
            session.commit()
        self._pending = []
        self.pending_names = []
        self.upload_log = []
        return rx.redirect("/profile")
   
    def load_profile(self):
        if self.new_user_id == 0:
            return rx.redirect("/login")
        with rx.session() as session:
            user = session.exec(select(Registration).where(Registration.id == self.new_user_id)).first()
            files = session.exec(select(Media.media_type, Media.file_name, Media.size_kb).where(Media.registration_id == self.new_user_id)).all()
        if user is None:
            self.reset_all()
            return rx.redirect("/login")
        parts = user.dob.split("/")
        self.profile_name = user.full_name
        self.profile_email = user.email
        self.profile_phone = user.phone
        self.profile_day = parts[0]
        self.profile_month = parts[1]
        self.profile_year = parts[2]
        self.profile_gender = user.gender
        self.profile_files = []
        for f in files:
            self.profile_files.append({"name": f.file_name, "type": f.media_type, "size": str(f.size_kb) + " KB"})
        self.editing = False
        self.changing_password = False
    def start_edit(self):
        self.editing = True
    def cancel_edit(self):
        self.editing = False
    def save_profile(self, form_data: dict):
        full_name = form_data["full_name"].strip()
        email = form_data["email"].strip().lower()
        phone = form_data["phone"].strip()
        gender = form_data["gender"]
        day = form_data["dob_day"]
        month = form_data["dob_month"]
        year = form_data["dob_year"]
        if not check_email(email): 
            self.open_popup("Error", "Please enter a valid email.")
            return 
        if not phone.isdigit() or len(phone) != 10:
            self.open_popup("Error", "Phone number must be 10 digits.")
            return
        if not self.check_dob(day, month, year):
            self.open_popup("Error", "Please select a valid date of birth.")
            return
        with rx.session() as session:
            if session.exec(select(Registration).where(Registration.email == email, Registration.id != self.new_user_id)).first():
                self.open_popup("Already Registered", "This email belongs to another user.")
                return
            if session.exec(select(Registration).where(Registration.phone == phone, Registration.id != self.new_user_id)).first():
                self.open_popup("Already Registered", "This phone number belongs to another user.")
                return
            user = session.exec(select(Registration).where(Registration.id == self.new_user_id)).first()
            user.full_name = full_name
            user.email = email
            user.phone = phone
            user.gender = gender
            user.dob = day + "/" + month + "/" + year
            session.add(user)
            session.commit()
        self.profile_name = full_name
        self.profile_email = email
        self.profile_phone = phone
        self.profile_gender = gender
        self.profile_day = day
        self.profile_month = month
        self.profile_year = year
        self.user_name = full_name.split(" ")[0]
        self.editing = False
        self.open_popup("Saved", "Your profile has been updated.")

    def start_password_change(self):
        self.changing_password = True
    def cancel_password_change(self):
        self.changing_password = False
    def change_password(self, form_data: dict):
        old_hash = hashlib.sha256(form_data["old_password"].encode()).hexdigest()
        new_password = form_data["new_password"]
        confirm = form_data["confirm_password"]
        with rx.session() as session:
            user = session.exec(select(Registration).where(Registration.id == self.new_user_id)).first()
            if user is None or user.password != old_hash:
                self.open_popup("Error", "Current password is incorrect.")
                return
            if new_password != confirm:
                self.open_popup("Error", "New passwords do not match.")
                return
            if len(new_password) < 6:
                self.open_popup("Error", "New password must be at least 6 characters.")
                return
            new_hash = hashlib.sha256(new_password.encode()).hexdigest()
            if new_hash == user.password:
                self.open_popup("Error", "New password must be different from the current one.")
                return
            user.password = new_hash
            session.add(user)
            session.commit()
        self.changing_password = False
        self.open_popup("Saved", "Your password has been changed.")
    def delete_profile(self):
        with rx.session() as session:
            for item in session.exec(select(Media).where(Media.registration_id == self.new_user_id)).all():
                session.delete(item)
            user = session.exec(select(Registration).where(Registration.id == self.new_user_id)).first()
            if user is not None:
                session.delete(user)
            session.commit()
        self.reset_all()
        self.open_popup("Deleted", "Your profile and files were deleted.")
        return rx.redirect("/")
#common components
def popup():
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title(State.popup_title),
            rx.alert_dialog.description(State.popup_message),
            rx.flex(rx.alert_dialog.cancel(rx.button("OK", on_click=State.close_popup)), justify="end", margin_top="1em")),open=State.show_popup)
def page(*children):
    return rx.center(rx.card(rx.vstack(*children, spacing="4", align="center")), popup(), min_height="100vh", padding_y="2em")
def info_row(label, value):
    return rx.hstack(rx.text(label, weight="bold", width="110px"), rx.text(value), width="100%")
def dob_row(day_value=None, month_value=None, year_value=None):
    return rx.hstack(
        rx.box(rx.select(days, name="dob_day", placeholder="Day", default_value=day_value, required=True, width="100%"), flex="1", min_width="0"),
        rx.box(rx.select(months, name="dob_month", placeholder="Month", default_value=month_value, required=True, width="100%"), flex="1.6", min_width="0"),
        rx.box(rx.select(years, name="dob_year", placeholder="Year", default_value=year_value, required=True, width="100%"), flex="1.2", min_width="0"),spacing="3",width="100%")
def gender_select(value=None):
    return rx.select(["Male", "Female", "Other"], name="gender", placeholder="Select Gender", default_value=value, required=True, width="100%")
#register
def index():
    form = rx.form(
        rx.vstack(
            rx.heading("Registration Form", size="6"),
            rx.input(name="full_name", placeholder="Full Name", required=True, width="100%"),
            rx.input(name="email", placeholder="Email", type="email", required=True, width="100%"),
            rx.input(name="phone", placeholder="Phone Number", required=True, width="100%"),
            rx.text("Date of Birth", size="2"),dob_row(),gender_select(),
            rx.input(name="password", placeholder="Password", type="password", required=True, width="100%"),
            rx.input(name="confirm_password", placeholder="Confirm Password", type="password", required=True, width="100%"),
            rx.button("Register", type="submit", width="100%"),
            rx.hstack(rx.text("Already registered?", size="2"), rx.link("Sign in", href="/login", size="2"), justify="center", width="100%"),spacing="3",width="340px"),on_submit=State.register)
    return page(form)
#login
def login_page():
    form = rx.form(
        rx.vstack(
            rx.heading("Sign In", size="6"),
            rx.text("Welcome back. Enter your details.", size="2"),
            rx.input(name="email", placeholder="Email", type="email", required=True, width="100%"),
            rx.input(name="password", placeholder="Password", type="password", required=True, width="100%"),
            rx.button("Sign in", type="submit", width="100%"),
            rx.hstack(rx.text("New here?", size="2"), rx.link("Register", href="/", size="2"), justify="center", width="100%"),spacing="3",width="340px"),on_submit=State.login)
    return page(form)
#upload
def upload_page():
    return page(
        rx.heading("Add your files", size="6"),
        rx.text("Welcome, " + State.user_name + ". Upload your files to finish.", size="2"),
        rx.upload(
            rx.text("Drag files here or click to select. You can add more at any time."),
            id="media_upload",multiple=True,max_files=max_files,max_size=max_size_mb * 1024 * 1024,on_drop=State.add_files(rx.upload_files(upload_id="media_upload")),border="1px dashed gray",padding="1em",width="340px"),
        rx.text("Ready to submit:", size="2", weight="bold"),
        rx.foreach(State.pending_names, lambda line: rx.text(line, size="2")),
        rx.foreach(State.upload_log, lambda line: rx.text(line, size="2", color="red")),
        rx.hstack(rx.button("Submit files", on_click=State.submit_files), rx.button("Clear list", on_click=State.clear_files, variant="soft")),
    )
#profile
def delete_dialog():
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(rx.button("Delete profile", color_scheme="red")),
        rx.alert_dialog.content(
            rx.alert_dialog.title("Delete profile?"),
            rx.alert_dialog.description("This permanently deletes your details and all your uploaded files. This cannot be undone."),
            rx.flex(
                rx.alert_dialog.cancel(rx.button("Cancel", variant="soft")),
                rx.alert_dialog.action(rx.button("Yes, delete", color_scheme="red", on_click=State.delete_profile)),spacing="3",justify="end",margin_top="1em")))
def profile_view():
    return rx.vstack(
        rx.heading("My Profile", size="6"),
        info_row("Full name", State.profile_name),
        info_row("Email", State.profile_email),
        info_row("Phone", State.profile_phone),
        info_row("Date of birth", State.profile_day + " " + State.profile_month + " " + State.profile_year),
        info_row("Gender", State.profile_gender),
        rx.text("My files", weight="bold"),
        rx.cond(State.profile_files.length() == 0, rx.text("No files uploaded yet.", size="2")),
        rx.foreach(State.profile_files, lambda f: rx.text(f["name"] + " - " + f["type"] + " - " + f["size"], size="2")),
        rx.flex(
            rx.button("Edit profile", on_click=State.start_edit),
            rx.button("Change password", on_click=State.start_password_change, variant="soft"),
            rx.button("Add more files", on_click=rx.redirect("/upload"), variant="soft"),
            rx.button("Log out", on_click=State.logout, variant="soft"),delete_dialog(),spacing="3",wrap="wrap"),spacing="3",width="340px")
def profile_edit():
    return rx.form(
        rx.vstack(
            rx.heading("Edit Profile", size="6"),
            rx.input(name="full_name", default_value=State.profile_name, placeholder="Full Name", required=True, width="100%"),
            rx.input(name="email", default_value=State.profile_email, placeholder="Email", type="email", required=True, width="100%"),
            rx.input(name="phone", default_value=State.profile_phone, placeholder="Phone Number", required=True, width="100%"),
            rx.text("Date of Birth", size="2"),dob_row(State.profile_day, State.profile_month, State.profile_year),gender_select(State.profile_gender),
            rx.hstack(rx.button("Save", type="submit"), rx.button("Cancel", type="button", on_click=State.cancel_edit, variant="soft"), spacing="3"),spacing="3",width="340px"),on_submit=State.save_profile)
def password_form():
    return rx.form(
        rx.vstack(
            rx.heading("Change Password", size="6"),
            rx.input(name="old_password", placeholder="Current password", type="password", required=True, width="100%"),
            rx.input(name="new_password", placeholder="New password", type="password", required=True, width="100%"),
            rx.input(name="confirm_password", placeholder="Confirm new password", type="password", required=True, width="100%"),
            rx.hstack(rx.button("Save password", type="submit"), rx.button("Cancel", type="button", on_click=State.cancel_password_change, variant="soft"), spacing="3"),spacing="3",width="340px"),on_submit=State.change_password)
def profile_page():
    return page(rx.cond(State.editing, profile_edit(), rx.cond(State.changing_password, password_form(), profile_view())))
app = rx.App(stylesheets=["/style.css"], style={"font_family": "Cambria, Georgia, serif"})
app.add_page(index, route="/")
app.add_page(login_page, route="/login")
app.add_page(upload_page, route="/upload", on_load=State.check_upload_page)
app.add_page(profile_page, route="/profile", on_load=State.load_profile)