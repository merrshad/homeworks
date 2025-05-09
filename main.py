import os
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

# تنظیمات برنامه Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here' # کلید محرمانه برای امنیت سشن‌ها
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db' # مسیر پایگاه داده SQLite
app.config['UPLOAD_FOLDER'] = 'uploads' # پوشه آپلود فایل‌ها
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'zip'} # فرمت‌های مجاز برای آپلود

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # صفحه‌ای که کاربر در صورت عدم احراز هویت به آن هدایت می‌شود
login_manager.login_message = 'لطفاً برای دسترسی به این صفحه وارد شوید.'
login_manager.login_message_category = 'info'

# مدل کاربر
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'دانشجو' یا 'استاد'

    # رابطه با تکالیف تعریف شده (برای استاد)
    defined_assignments = db.relationship('DefinedAssignment', backref='teacher', lazy=True)

    # رابطه با تکالیف ارسال شده (برای دانشجو)
    submissions = db.relationship('Submission', backref='student', lazy=True)

    def __repr__(self):
        return f"User('{self.email}', '{self.role}')"

# مدل تکلیف تعریف شده توسط استاد
class DefinedAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    course = db.Column(db.String(100), nullable=True)
    created_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    deadline = db.Column(db.DateTime, nullable=True) # مهلت ارسال
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # رابطه با فایل‌های ارسالی دانشجویان برای این تکلیف
    submissions = db.relationship('Submission', backref='defined_assignment', lazy=True)

    def __repr__(self):
        return f"DefinedAssignment('{self.title}', '{self.course}')"

# مدل ارسال تکلیف توسط دانشجو
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(150), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    defined_assignment_id = db.Column(db.Integer, db.ForeignKey('defined_assignment.id'), nullable=False)

    def __repr__(self):
        return f"Submission('{self.filename}', '{self.upload_date}')"

# تابع لود کردن کاربر برای Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# تابع کمکی برای بررسی فرمت فایل مجاز
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# مسیر اصلی (می‌تواند به صفحه ورود هدایت کند)
@app.route('/')
def index():
    return redirect(url_for('login'))

# مسیر ورود کاربران
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'دانشجو':
            return redirect(url_for('student_dashboard'))
        elif current_user.role == 'استاد':
            return redirect(url_for('teacher_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == 'دانشجو':
                return redirect(url_for('student_dashboard'))
            elif user.role == 'استاد':
                return redirect(url_for('teacher_dashboard'))
        else:
            flash('ورود ناموفق. لطفاً ایمیل و رمز عبور خود را بررسی کنید.', 'danger')
    
    return render_template('login.html')

# مسیر ثبت‌نام کاربران
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        if current_user.role == 'دانشجو':
            return redirect(url_for('student_dashboard'))
        elif current_user.role == 'استاد':
            return redirect(url_for('teacher_dashboard'))

    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role') # 'دانشجو' یا 'استاد'

        hashed_password = generate_password_hash(password)
        
        # بررسی وجود کاربر با ایمیل مشابه
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('کاربری با این ایمیل قبلاً ثبت‌نام کرده است.', 'warning')
            return redirect(url_for('register'))

        new_user = User(first_name=first_name, last_name=last_name, email=email, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('حساب کاربری شما با موفقیت ایجاد شد. اکنون می‌توانید وارد شوید.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# مسیر خروج کاربران
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# مسیر داشبورد دانشجو
@app.route('/student')
@login_required
def student_dashboard():
    if current_user.role != 'دانشجو':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index')) # هدایت به صفحه اصلی یا ورود

    # دریافت تمام تکالیف تعریف شده توسط استاد
    defined_assignments = DefinedAssignment.query.all()
    # دریافت تکالیف ارسال شده توسط دانشجو
    student_submissions = Submission.query.filter_by(student_id=current_user.id).all()

    # ایجاد دیکشنری برای دسترسی آسان به سابمیشن‌های دانشجو بر اساس ID تکلیف
    # این کمک می‌کند تا در تمپلیت مشخص کنیم آیا دانشجو برای تکلیفی فایل ارسال کرده یا خیر
    submitted_assignment_ids = {sub.defined_assignment_id for sub in student_submissions}

    return render_template('student_dashboard.html', 
                           defined_assignments=defined_assignments,
                           student_submissions=student_submissions,
                           submitted_assignment_ids=submitted_assignment_ids,
                           datetime=datetime)

# مسیر داشبورد استاد
@app.route('/teacher')
@login_required
def teacher_dashboard():
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index')) # هدایت به صفحه اصلی یا ورود

    # دریافت تمام تکالیف تعریف شده توسط این استاد
    teachers_defined_assignments = DefinedAssignment.query.filter_by(teacher_id=current_user.id).all()

    # دریافت تمام سابمیشن‌ها
    all_submissions = Submission.query.all()

    return render_template('teacher_dashboard.html', 
                           defined_assignments=teachers_defined_assignments,
                           submissions=all_submissions,
                           datetime=datetime)

# مسیر ایجاد تکلیف جدید توسط استاد
@app.route('/teacher/create_assignment', methods=['GET', 'POST'])
@login_required
def create_assignment():
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        course = request.form.get('course')
        deadline_str = request.form.get('deadline')

        deadline = None
        if deadline_str:
            try:
                # فرمت ورودی datetime-local از HTML: YYYY-MM-DDTHH:MM
                deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('فرمت تاریخ و زمان مهلت صحیح نیست.', 'danger')
                return redirect(url_for('teacher_dashboard')) # یا رندر کردن مجدد فرم با خطا


        new_defined_assignment = DefinedAssignment(title=title, description=description, course=course, deadline=deadline, teacher_id=current_user.id)
        db.session.add(new_defined_assignment)
        db.session.commit()
        flash('تکلیف جدید با موفقیت ایجاد شد.', 'success')
        return redirect(url_for('teacher_dashboard'))

    # در متد GET، فرم ایجاد تکلیف نمایش داده می‌شود. این باید در تمپلیت استاد باشد.
    # این مسیر برای نمایش فرم به تنهایی نیست و فقط برای پردازش POST استفاده می‌شود.
    return redirect(url_for('teacher_dashboard'))

# مسیر ویرایش تکلیف توسط استاد
@app.route('/teacher/edit_assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def edit_assignment(assignment_id):
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    defined_assignment = DefinedAssignment.query.get_or_404(assignment_id)

    # اطمینان از اینکه استاد فعلی سازنده این تکلیف است
    if defined_assignment.teacher_id != current_user.id:
         flash('شما اجازه ویرایش این تکلیف را ندارید.', 'danger')
         return redirect(url_for('teacher_dashboard'))

    if request.method == 'POST':
        defined_assignment.title = request.form.get('title')
        defined_assignment.description = request.form.get('description')
        defined_assignment.course = request.form.get('course')
        deadline_str = request.form.get('deadline')

        deadline = None
        if deadline_str:
            try:
                defined_assignment.deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('فرمت تاریخ و زمان مهلت صحیح نیست.', 'danger')
                return render_template('edit_assignment.html', assignment=defined_assignment) # رندر مجدد فرم با خطا
        else:
             defined_assignment.deadline = None # اگر فیلد خالی ارسال شود مهلت حذف می‌شود

        db.session.commit()
        flash('تکلیف با موفقیت ویرایش شد.', 'success')
        return redirect(url_for('teacher_dashboard'))

    # در متد GET، فرم ویرایش نمایش داده می‌شود
    return render_template('edit_assignment.html', assignment=defined_assignment)


# مسیر نمایش سابمیشن‌های یک تکلیف خاص (برای استاد)
@app.route('/teacher/assignment_submissions/<int:assignment_id>')
@login_required
def assignment_submissions(assignment_id):
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    defined_assignment = DefinedAssignment.query.get_or_404(assignment_id)

    # اطمینان از اینکه استاد فعلی سازنده این تکلیف است (اختیاری اما توصیه می‌شود)
    if defined_assignment.teacher_id != current_user.id:
         flash('شما اجازه دسترسی به سابمیشن‌های این تکلیف را ندارید.', 'danger')
         return redirect(url_for('teacher_dashboard'))

    # دریافت تمام سابمیشن‌ها برای این تکلیف خاص
    submissions = Submission.query.filter_by(defined_assignment_id=assignment_id).all()

    return render_template('assignment_submissions.html', 
                           defined_assignment=defined_assignment,
                           submissions=submissions)

# مسیر آپلود تکلیف توسط دانشجو
@app.route('/upload', methods=['POST'])
@login_required
def upload_assignment():
    if current_user.role != 'دانشجو':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    # شناسه تکلیف تعریف شده که دانشجو برای آن فایل ارسال می‌کند
    defined_assignment_id = request.form.get('defined_assignment_id')
    if not defined_assignment_id:
         flash('شناسه تکلیف مشخص نشده است.', 'danger')
         return redirect(url_for('student_dashboard'))

    defined_assignment = DefinedAssignment.query.get(defined_assignment_id)
    if not defined_assignment:
         flash('تکلیف مشخص شده وجود ندارد.', 'danger')
         return redirect(url_for('student_dashboard'))

    # !!! بررسی مهلت ارسال تکلیف !!!
    if defined_assignment.deadline and datetime.utcnow() > defined_assignment.deadline:
        flash('مهلت ارسال این تکلیف به پایان رسیده است.', 'danger')
        return redirect(url_for('student_dashboard'))

    # بررسی وجود فایل در درخواست
    if 'assignment_file' not in request.files:
        flash('فایلی برای آپلود انتخاب نشده است.', 'danger')
        return redirect(url_for('student_dashboard'))

    file = request.files['assignment_file']

    # اگر کاربر فایلی انتخاب نکرده و فیلد خالی باشد
    if file.filename == '':
        flash('فایلی انتخاب نشده است.', 'danger')
        return redirect(url_for('student_dashboard'))

    # اگر فایل انتخاب شده و فرمت آن مجاز باشد
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)

        # اطمینان از یونیک بودن نام فایل یا استفاده از روش دیگر برای جلوگیری از تداخل
        # در حال حاضر فرض می‌کنیم نام فایل کافی است.
        # می‌توانید از uuid یا ترکیب user_id و assignment_id استفاده کنید.

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # اگر فایلی با همین نام از قبل وجود دارد (ممکن است باعث مشکل شود) - نیاز به مدیریت بهتر نام فایل
        # برای سادگی در حال حاضر نادیده گرفته می‌شود، اما در پروژه واقعی باید مدیریت شود.

        try:
            file.save(file_path)

            # ذخیره اطلاعات در دیتابیس Submission
            new_submission = Submission(filename=filename, 
                                        student_id=current_user.id, 
                                        defined_assignment_id=defined_assignment.id)
            db.session.add(new_submission)
            db.session.commit()

            flash('تکلیف با موفقیت آپلود شد.', 'success')
            return redirect(url_for('student_dashboard'))
        except Exception as e:
            # مدیریت خطای ذخیره فایل
            flash(f'خطا در ذخیره فایل: {e}', 'danger')
            return redirect(url_for('student_dashboard'))
    else:
        flash('فرمت فایل مجاز نیست.', 'danger')
        return redirect(url_for('student_dashboard'))


# مسیر دانلود فایل برای استاد
@app.route('/download/<filename>')
@login_required
def download_file(filename):
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    # اختیاری: بررسی کنید که آیا فایل مربوط به یک سابمیشن معتبر است یا خیر
    # submission = Submission.query.filter_by(filename=filename).first()
    # if not submission:
    #     flash('فایل مورد نظر یافت نشد یا مرتبط با سابمیشن معتبری نیست.', 'danger')
    #     return redirect(url_for('teacher_dashboard'))

    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        flash('فایل مورد نظر یافت نشد.', 'danger')
        return redirect(url_for('teacher_dashboard'))

# ایجاد جداول پایگاه داده در صورت عدم وجود (پس از تعریف مدل‌های جدید)
# توجه: اگر قبلاً جداول را ایجاد کرده‌اید، ممکن است نیاز به حذف فایل site.db و اجرای مجدد داشته باشید
# یا از Flask-Migrate برای مدیریت تغییرات دیتابیس استفاده کنید.
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # اطمینان از وجود پوشه آپلود
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
