import os
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_migrate import Migrate

# تنظیمات برنامه Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here' # کلید محرمانه برای امنیت سشن‌ها
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db' # مسیر پایگاه داده SQLite
app.config['UPLOAD_FOLDER'] = 'uploads' # پوشه آپلود فایل‌ها
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'zip'} # فرمت‌های مجاز برای آپلود

db = SQLAlchemy(app)
migrate = Migrate(app, db)
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

    # رابطه با درس‌هایی که استاد تدریس می‌کند
    taught_courses = db.relationship('Course', backref='teacher', lazy=True)

    # رابطه با تکالیف تعریف شده (برای استاد)
    defined_assignments = db.relationship('DefinedAssignment', backref='teacher', lazy=True)

    # رابطه با تکالیف ارسال شده (برای دانشجو)
    submissions = db.relationship('Submission', backref='student', lazy=True)

    # رابطه با اعلان‌ها
    notifications = db.relationship('Notification', backref='user', lazy=True)

    def __repr__(self):
        return f"User('{self.email}', '{self.role}')"

# مدل درس
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # رابطه با تکالیف مربوط به این درس
    assignments = db.relationship('DefinedAssignment', backref='course', lazy=True, cascade="all, delete-orphan")
    
    # رابطه با دانشجویان ثبت‌نام شده
    enrolled_students = db.relationship('CourseEnrollment', backref='course', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Course('{self.name}')"

# مدل تکلیف تعریف شده توسط استاد
class DefinedAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    attachment_path = db.Column(db.String(255))  # مسیر فایل پیوست
    
    submissions = db.relationship('Submission', backref='defined_assignment', lazy=True)

    def __repr__(self):
        return f"DefinedAssignment('{self.title}', '{self.course.name if self.course else 'N/A'}')"

# مدل ارسال تکلیف توسط دانشجو
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(150), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    grade = db.Column(db.String(10), nullable=True) # فیلد نمره (می‌تواند رشته برای Pass/Fail یا عدد باشد)
    feedback = db.Column(db.Text, nullable=True) # فیلد بازخورد استاد
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    defined_assignment_id = db.Column(db.Integer, db.ForeignKey('defined_assignment.id'), nullable=False)

    def __repr__(self):
        return f"Submission('{self.filename}', '{self.upload_date}')"

# مدل اعلان‌ها
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    type = db.Column(db.String(20), nullable=False)  # 'assignment', 'grade', 'message', etc.

    def __repr__(self):
        return f"Notification('{self.title}', '{self.created_date}')"

# مدل پیام‌ها
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    related_assignment_id = db.Column(db.Integer, db.ForeignKey('defined_assignment.id'), nullable=True)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

    def __repr__(self):
        return f"Message('{self.sender.email} -> {self.receiver.email}', '{self.created_date}')"

# مدل آمار و گزارش‌ها
class CourseStatistics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_assignments = db.Column(db.Integer, default=0)
    total_submissions = db.Column(db.Integer, default=0)
    average_grade = db.Column(db.Float, default=0.0)
    last_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # رابطه با استاد
    teacher = db.relationship('User', backref='course_statistics', lazy=True)

    def __repr__(self):
        return f"CourseStatistics('{self.course.name}', '{self.last_updated}')"

# مدل ثبت‌نام در درس
class CourseEnrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    enrollment_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # ایجاد رابطه با دانشجو
    student = db.relationship('User', backref='enrollments')
    
    # ایجاد یک unique constraint برای جلوگیری از ثبت‌نام تکراری
    __table_args__ = (
        db.UniqueConstraint('student_id', 'course_id', name='unique_student_course'),
    )

    def __repr__(self):
        return f"CourseEnrollment(student_id={self.student_id}, course_id={self.course_id})"

# مدل جزوه درس
class CourseMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    course = db.relationship('Course', backref=db.backref('materials', lazy=True))
    teacher = db.relationship('User', backref=db.backref('uploaded_materials', lazy=True))

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
        return redirect(url_for('index'))

    # دریافت درس‌هایی که دانشجو در آن‌ها ثبت‌نام کرده
    enrolled_courses = CourseEnrollment.query.filter_by(student_id=current_user.id).all()
    enrolled_course_ids = [enrollment.course_id for enrollment in enrolled_courses]

    # دریافت تکالیف درس‌های ثبت‌نام شده
    defined_assignments = DefinedAssignment.query.filter(
        DefinedAssignment.course_id.in_(enrolled_course_ids)
    ).all()

    # دریافت تکالیف ارسال شده توسط دانشجو
    student_submissions = Submission.query.filter_by(student_id=current_user.id).all()

    # ایجاد دیکشنری برای دسترسی آسان به سابمیشن‌های دانشجو بر اساس ID تکلیف
    submitted_assignment_ids = {sub.defined_assignment_id for sub in student_submissions}
    submission_by_assignment = {sub.defined_assignment_id: sub for sub in student_submissions}

    return render_template('student_dashboard.html', 
                         defined_assignments=defined_assignments,
                         student_submissions=student_submissions,
                         submitted_assignment_ids=submitted_assignment_ids,
                         submission_by_assignment=submission_by_assignment,
                         datetime=datetime)

# مسیر داشبورد استاد
@app.route('/teacher')
@login_required
def teacher_dashboard():
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index')) # هدایت به صفحه اصلی یا ورود

    # دریافت تمام درس‌های این استاد
    teachers_courses = Course.query.filter_by(teacher_id=current_user.id).all()
    # دریافت تمام تکالیف تعریف شده توسط این استاد (برای نمایش در داشبورد کلی)
    teachers_defined_assignments = DefinedAssignment.query.filter_by(teacher_id=current_user.id).all()

    # دریافت تمام سabmissions
    all_submissions = Submission.query.all()

    return render_template('teacher_dashboard.html', 
                           courses=teachers_courses,
                           defined_assignments=teachers_defined_assignments, # ممکن است دیگر لازم نباشد همه تکالیف اینجا نمایش داده شوند
                           submissions=all_submissions, # ممکن است دیگر لازم نباشد همه سابمیشن‌ها اینجا نمایش داده شوند
                           datetime=datetime)

# مسیر مدیریت درس‌ها توسط استاد
@app.route('/teacher/courses')
@login_required
def manage_courses():
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))
    
    teachers_courses = Course.query.filter_by(teacher_id=current_user.id).all()
    return render_template('manage_courses.html', courses=teachers_courses)

# مسیر ایجاد درس جدید توسط استاد
@app.route('/teacher/create_course', methods=['GET', 'POST'])
@login_required
def create_course():
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        course_name = request.form.get('name')
        if not course_name:
            flash('نام درس نمی‌تواند خالی باشد.', 'danger')
            return redirect(url_for('manage_courses')) # یا رندر کردن مجدد فرم

        new_course = Course(name=course_name, teacher_id=current_user.id)
        db.session.add(new_course)
        db.session.commit()
        flash('درس جدید با موفقیت ایجاد شد.', 'success')
        return redirect(url_for('manage_courses'))
    
    # در متد GET، فرم ایجاد درس نمایش داده می‌شود. این می‌تواند در تمپلیت manage_courses باشد.
    return redirect(url_for('manage_courses'))

# مسیر ویرایش درس توسط استاد
@app.route('/teacher/edit_course/<int:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    course = Course.query.get_or_404(course_id)

    # اطمینان از اینکه استاد فعلی صاحب این درس است
    if course.teacher_id != current_user.id:
        flash('شما اجازه ویرایش این درس را ندارید.', 'danger')
        return redirect(url_for('manage_courses'))

    if request.method == 'POST':
        course.name = request.form.get('name')
        if not course.name:
             flash('نام درس نمی‌تواند خالی باشد.', 'danger')
             return render_template('edit_course.html', course=course) # رندر مجدد فرم با خطا

        db.session.commit()
        flash('درس با موفقیت ویرایش شد.', 'success')
        return redirect(url_for('manage_courses'))

    return render_template('edit_course.html', course=course)

# مسیر حذف درس توسط استاد
@app.route('/teacher/delete_course/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id):
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    course = Course.query.get_or_404(course_id)

    # اطمینان از اینکه استاد فعلی صاحب این درس است
    if course.teacher_id != current_user.id:
        flash('شما اجازه حذف این درس را ندارید.', 'danger')
        return redirect(url_for('manage_courses'))

    try:
        # به دلیل cascade در مدل Course، تکالیف و سابمیشن‌های مرتبط نیز حذف می‌شوند
        db.session.delete(course)
        db.session.commit()
        flash('درس با موفقیت حذف شد.', 'success')
    except Exception as e:
        flash(f'خطا در حذف درس: {e}', 'danger')

    return redirect(url_for('manage_courses'))


# مسیر ایجاد تکلیف جدید توسط استاد (نیاز به انتخاب درس)
@app.route('/teacher/create_assignment', methods=['GET', 'POST'])
@login_required
def create_assignment():
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        course_id = request.form.get('course_id')
        title = request.form.get('title')
        description = request.form.get('description')
        deadline_str = request.form.get('deadline')
        
        if not all([course_id, title]):
            flash('لطفاً تمام فیلدهای الزامی را پر کنید.', 'danger')
            return redirect(url_for('create_assignment'))
        
        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('فرمت تاریخ نامعتبر است.', 'danger')
                return redirect(url_for('create_assignment'))
        
        attachment_path = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'assignments', filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                file.save(file_path)
                attachment_path = file_path
        
        assignment = DefinedAssignment(
            title=title,
            description=description,
            deadline=deadline,
            course_id=course_id,
            teacher_id=current_user.id,
            attachment_path=attachment_path
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        # ایجاد اعلان برای دانشجویان
        course = Course.query.get(course_id)
        for enrollment in course.enrolled_students:
            create_notification(
                user_id=enrollment.student_id,
                title='تکلیف جدید',
                message=f'تکلیف جدید "{title}" برای درس {course.name} تعریف شد.',
                link=url_for('view_assignment', assignment_id=assignment.id)
            )
        
        flash('تکلیف با موفقیت ایجاد شد.', 'success')
        return redirect(url_for('teacher_dashboard'))
    
    courses = Course.query.filter_by(teacher_id=current_user.id).all()
    return render_template('create_assignment.html', courses=courses)


# مسیر ویرایش تکلیف توسط استاد (نیاز به انتخاب درس)
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
    
    teachers_courses = Course.query.filter_by(teacher_id=current_user.id).all()
    if not teachers_courses:
        flash('شما درسی برای ویرایش تکلیف ندارید. ابتدا یک درس ایجاد کنید.', 'warning')
        return redirect(url_for('manage_courses')) # یا هدایت به داشبورد استاد


    if request.method == 'POST':
        defined_assignment.title = request.form.get('title')
        defined_assignment.description = request.form.get('description')
        course_id = request.form.get('course_id')
        deadline_str = request.form.get('deadline')

        # بررسی وجود درس انتخاب شده
        course = Course.query.get(course_id)
        if not course or course.teacher_id != current_user.id:
            flash('درس انتخاب شده نامعتبر است.', 'danger')
            return render_template('edit_assignment.html', assignment=defined_assignment, courses=teachers_courses)

        defined_assignment.course_id = course.id

        deadline = None
        if deadline_str:
            try:
                defined_assignment.deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('فرمت تاریخ و زمان مهلت صحیح نیست.', 'danger')
                return render_template('edit_assignment.html', assignment=defined_assignment, courses=teachers_courses) # رندر مجدد فرم با خطا
        else:
             defined_assignment.deadline = None # اگر فیلد خالی ارسال شود مهلت حذف می‌شود

        db.session.commit()
        flash('تکلیف با موفقیت ویرایش شد.', 'success')
        return redirect(url_for('teacher_dashboard')) # یا هدایت به صفحه جزئیات تکلیف یا داشبورد استاد

    # در متد GET، فرم ویرایش نمایش داده می‌شود
    return render_template('edit_assignment.html', assignment=defined_assignment, courses=teachers_courses)

# مسیر حذف تکلیف توسط استاد
@app.route('/teacher/delete_assignment/<int:assignment_id>', methods=['POST'])
@login_required
def delete_assignment(assignment_id):
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    defined_assignment = DefinedAssignment.query.get_or_404(assignment_id)

    # اطمینان از اینکه استاد فعلی سازنده این تکلیف است
    if defined_assignment.teacher_id != current_user.id:
         flash('شما اجازه حذف این تکلیف را ندارید.', 'danger')
         return redirect(url_for('teacher_dashboard'))

    try:
        # حذف سابمیشن‌های مرتبط با این تکلیف نیز به دلیل cascade در مدل
        db.session.delete(defined_assignment)
        db.session.commit()
        flash('تکلیف با موفقیت حذف شد.', 'success')
    except Exception as e:
        flash(f'خطا در حذف تکلیف: {e}', 'danger')

    return redirect(url_for('teacher_dashboard'))


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

# مسیر نمره‌دهی به سابمیشن توسط استاد
@app.route('/teacher/grade_submission/<int:submission_id>', methods=['GET', 'POST'])
@login_required
def grade_submission(submission_id):
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    submission = Submission.query.get_or_404(submission_id)
    
    # اطمینان از اینکه استاد فعلی صاحب تکلیفی است که این سابمیشن برای آن ارسال شده
    if submission.defined_assignment.teacher_id != current_user.id:
        flash('شما اجازه نمره‌دهی به این سابمیشن را ندارید.', 'danger')
        return redirect(url_for('teacher_dashboard')) # یا ریدایرکت به صفحه سابمیشن‌های همان تکلیف

    if request.method == 'POST':
        grade = request.form.get('grade')
        feedback = request.form.get('feedback')

        submission.grade = grade
        submission.feedback = feedback
        db.session.commit()

        flash('نمره و بازخورد با موفقیت ثبت شد.', 'success')
        # ریدایرکت به صفحه سابمیشن‌های همان تکلیف
        return redirect(url_for('assignment_submissions', assignment_id=submission.defined_assignment.id))

    # در متد GET، فرم نمره‌دهی نمایش داده می‌شود
    return render_template('grade_submission.html', submission=submission)

@app.route('/student/upload_assignment', methods=['POST'])
@login_required
def upload_assignment():
    if current_user.role != 'دانشجو':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    if 'assignment_file' not in request.files:
        flash('فایلی برای آپلود انتخاب نشده است.', 'warning')
        return redirect(url_for('student_dashboard'))

    file = request.files['assignment_file']
    defined_assignment_id = request.form.get('defined_assignment_id')

    if not file.filename:
        flash('فایل انتخاب شده نامعتبر است.', 'warning')
        return redirect(url_for('student_dashboard'))

    if file and allowed_file(file.filename) and defined_assignment_id:
        # Check if assignment exists and is still open for submission (optional but recommended)
        defined_assignment = DefinedAssignment.query.get(defined_assignment_id)
        if not defined_assignment:
            flash('تکلیف مورد نظر یافت نشد.', 'danger')
            return redirect(url_for('student_dashboard'))

        # Check if deadline has passed (optional but recommended)
        if defined_assignment.deadline and datetime.utcnow() > defined_assignment.deadline:
            flash('مهلت ارسال این تکلیف به پایان رسیده است.', 'danger')
            return redirect(url_for('student_dashboard'))
            
        # Prevent multiple submissions for the same assignment by the same student (optional)
        existing_submission = Submission.query.filter_by(student_id=current_user.id, defined_assignment_id=defined_assignment_id).first()
        if existing_submission:
            flash('شما قبلاً برای این تکلیف فایلی ارسال کرده‌اید.', 'warning')
            return redirect(url_for('student_dashboard'))

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        new_submission = Submission(filename=filename, student_id=current_user.id, defined_assignment_id=defined_assignment_id)
        db.session.add(new_submission)
        db.session.commit()

        flash('تکلیف با موفقیت آپلود شد.', 'success')
        return redirect(url_for('student_dashboard'))
    else:
        flash('فرمت فایل مجاز نیست یا مشکلی در ارسال وجود دارد.', 'danger')

    return redirect(url_for('student_dashboard'))

# مسیر نمایش جزئیات یک submission (برای استاد و دانشجو)
@app.route('/submission/<int:submission_id>')
@login_required
def view_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)

    # اطمینان از اینکه کاربر فعلی یا استاد مربوطه می‌تواند این سابمیشن را ببیند
    if current_user.role == 'دانشجو' and submission.student_id != current_user.id:
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('student_dashboard')) # یا صفحه اصلی دانشجو

    if current_user.role == 'استاد' and submission.defined_assignment.teacher_id != current_user.id:
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('teacher_dashboard')) # یا صفحه اصلی استاد

    return render_template('view_submission.html', submission=submission)


# مسیر دانلود فایل سابمیشن
@app.route('/uploads/<filename>')
@login_required # شاید نیاز به بررسی بیشتر دسترسی باشد که فقط استاد مربوطه یا دانشجو صاحب سابمیشن بتواند دانلود کند
def uploaded_file(filename):
    # یک لایه امنیتی اضافه کنید: اطمینان حاصل کنید که کاربر فعلی مجاز به دانلود این فایل است
    # مثلاً اگر دانشجو است، باید صاحب سابمیشنی باشد که این فایل به آن مرتبط است.
    # اگر استاد است، باید صاحب تکلیفی باشد که سابمیشن مربوط به آن است.
    # فعلاً به سادگی اجازه دانلود برای کاربران لاگین شده داده می‌شود.
    # پیاده‌سازی دقیق‌تر بررسی دسترسی به عهده شماست.
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        abort(404)

# مسیرهای مربوط به اعلان‌ها
@app.route('/notifications')
@login_required
def notifications():
    user_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_date.desc()).all()
    return render_template('notifications.html', notifications=user_notifications)

@app.route('/notifications/mark_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        flash('شما اجازه دسترسی به این اعلان را ندارید.', 'danger')
        return redirect(url_for('notifications'))
    
    notification.is_read = True
    db.session.commit()
    return redirect(url_for('notifications'))

# مسیرهای مربوط به پیام‌ها
@app.route('/messages')
@login_required
def messages():
    received_messages = Message.query.filter_by(receiver_id=current_user.id).order_by(Message.created_date.desc()).all()
    sent_messages = Message.query.filter_by(sender_id=current_user.id).order_by(Message.created_date.desc()).all()
    return render_template('messages.html', received_messages=received_messages, sent_messages=sent_messages)

@app.route('/messages/send', methods=['GET', 'POST'])
@login_required
def send_message():
    if request.method == 'POST':
        receiver_id = request.form.get('receiver_id')
        content = request.form.get('content')
        assignment_id = request.form.get('assignment_id')
        
        new_message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=content,
            related_assignment_id=assignment_id if assignment_id else None
        )
        
        # ایجاد اعلان برای گیرنده
        receiver = User.query.get(receiver_id)
        notification = Notification(
            user_id=receiver_id,
            title='پیام جدید',
            message=f'شما یک پیام جدید از {current_user.first_name} {current_user.last_name} دریافت کردید.',
            type='message'
        )
        
        db.session.add(new_message)
        db.session.add(notification)
        db.session.commit()
        
        flash('پیام شما با موفقیت ارسال شد.', 'success')
        return redirect(url_for('messages'))
    
    # در حالت GET، لیست کاربران را برای انتخاب گیرنده نمایش می‌دهیم
    if current_user.role == 'استاد':
        users = User.query.filter_by(role='دانشجو').all()
    else:
        users = User.query.filter_by(role='استاد').all()
    
    return render_template('send_message.html', users=users)

# مسیرهای مربوط به آمار و گزارش‌ها
@app.route('/statistics')
@login_required
def statistics():
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))
    
    # آمار کلی
    total_courses = Course.query.filter_by(teacher_id=current_user.id).count()
    total_assignments = DefinedAssignment.query.join(Course).filter(Course.teacher_id == current_user.id).count()
    total_submissions = Submission.query.join(DefinedAssignment).join(Course).filter(Course.teacher_id == current_user.id).count()
    
    # آمار به تفکیک درس
    course_stats = []
    for course in Course.query.filter_by(teacher_id=current_user.id).all():
        assignments = DefinedAssignment.query.filter_by(course_id=course.id).all()
        total_course_submissions = sum(len(assignment.submissions) for assignment in assignments)
        avg_grade = 0
        total_graded = 0
        
        for assignment in assignments:
            for submission in assignment.submissions:
                if submission.grade:
                    try:
                        avg_grade += float(submission.grade)
                        total_graded += 1
                    except ValueError:
                        pass
        
        avg_grade = avg_grade / total_graded if total_graded > 0 else 0
        
        course_stats.append({
            'course': course,
            'total_assignments': len(assignments),
            'total_submissions': total_course_submissions,
            'average_grade': round(avg_grade, 2)
        })
    
    return render_template('statistics.html',
                         total_courses=total_courses,
                         total_assignments=total_assignments,
                         total_submissions=total_submissions,
                         course_stats=course_stats)

# تابع کمکی برای ایجاد اعلان
def create_notification(user_id, title, message, type):
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=type
    )
    db.session.add(notification)
    db.session.commit()

# مسیر مدیریت ثبت‌نام در درس
@app.route('/teacher/course/<int:course_id>/enrollments', methods=['GET', 'POST'])
@login_required
def manage_course_enrollments(course_id):
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash('شما اجازه مدیریت این درس را ندارید.', 'danger')
        return redirect(url_for('manage_courses'))

    if request.method == 'POST':
        student_id = request.form.get('student_id')
        action = request.form.get('action')

        if action == 'enroll':
            # بررسی وجود دانشجو
            student = User.query.filter_by(id=student_id, role='دانشجو').first()
            if not student:
                flash('دانشجوی مورد نظر یافت نشد.', 'danger')
                return redirect(url_for('manage_course_enrollments', course_id=course_id))

            # بررسی ثبت‌نام تکراری
            existing_enrollment = CourseEnrollment.query.filter_by(
                student_id=student_id,
                course_id=course_id
            ).first()

            if existing_enrollment:
                flash('این دانشجو قبلاً در این درس ثبت‌نام کرده است.', 'warning')
            else:
                new_enrollment = CourseEnrollment(student_id=student_id, course_id=course_id)
                db.session.add(new_enrollment)
                db.session.commit()
                flash('دانشجو با موفقیت در درس ثبت‌نام شد.', 'success')

        elif action == 'unenroll':
            enrollment = CourseEnrollment.query.filter_by(
                student_id=student_id,
                course_id=course_id
            ).first()

            if enrollment:
                db.session.delete(enrollment)
                db.session.commit()
                flash('دانشجو با موفقیت از درس حذف شد.', 'success')
            else:
                flash('این دانشجو در این درس ثبت‌نام نکرده است.', 'warning')

        return redirect(url_for('manage_course_enrollments', course_id=course_id))

    # دریافت لیست دانشجویان ثبت‌نام شده
    enrolled_students = CourseEnrollment.query.filter_by(course_id=course_id).all()
    enrolled_student_ids = [enrollment.student_id for enrollment in enrolled_students]

    # دریافت لیست تمام دانشجویان
    all_students = User.query.filter_by(role='دانشجو').all()

    return render_template('manage_course_enrollments.html',
                         course=course,
                         enrolled_students=enrolled_students,
                         all_students=all_students,
                         enrolled_student_ids=enrolled_student_ids)

# مسیر نمایش درس‌های قابل ثبت‌نام برای دانشجو
@app.route('/student/available_courses')
@login_required
def available_courses():
    if current_user.role != 'دانشجو':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    # دریافت درس‌هایی که دانشجو در آن‌ها ثبت‌نام کرده
    enrolled_courses = CourseEnrollment.query.filter_by(student_id=current_user.id).all()
    enrolled_course_ids = [enrollment.course_id for enrollment in enrolled_courses]

    # دریافت تمام درس‌های موجود به جز درس‌هایی که دانشجو در آن‌ها ثبت‌نام کرده
    available_courses = Course.query.filter(~Course.id.in_(enrolled_course_ids)).all()

    return render_template('available_courses.html', 
                         available_courses=available_courses,
                         enrolled_courses=enrolled_courses)

# مسیر ثبت‌نام دانشجو در درس
@app.route('/student/enroll_course/<int:course_id>', methods=['POST'])
@login_required
def enroll_course(course_id):
    if current_user.role != 'دانشجو':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    # بررسی وجود درس
    course = Course.query.get_or_404(course_id)

    # بررسی ثبت‌نام تکراری
    existing_enrollment = CourseEnrollment.query.filter_by(
        student_id=current_user.id,
        course_id=course_id
    ).first()

    if existing_enrollment:
        flash('شما قبلاً در این درس ثبت‌نام کرده‌اید.', 'warning')
    else:
        new_enrollment = CourseEnrollment(student_id=current_user.id, course_id=course_id)
        db.session.add(new_enrollment)
        db.session.commit()
        flash('شما با موفقیت در درس ثبت‌نام شدید.', 'success')

    return redirect(url_for('available_courses'))

# مسیر لغو ثبت‌نام دانشجو از درس
@app.route('/student/unenroll_course/<int:course_id>', methods=['POST'])
@login_required
def unenroll_course(course_id):
    if current_user.role != 'دانشجو':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    enrollment = CourseEnrollment.query.filter_by(
        student_id=current_user.id,
        course_id=course_id
    ).first()

    if enrollment:
        db.session.delete(enrollment)
        db.session.commit()
        flash('ثبت‌نام شما در درس با موفقیت لغو شد.', 'success')
    else:
        flash('شما در این درس ثبت‌نام نکرده‌اید.', 'warning')

    return redirect(url_for('available_courses'))

# مسیرهای جدید برای مدیریت جزوات درسی
@app.route('/teacher/course/<int:course_id>/materials', methods=['GET', 'POST'])
@login_required
def manage_course_materials(course_id):
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))
    
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash('شما اجازه دسترسی به این درس را ندارید.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if 'material_file' not in request.files:
            flash('فایل انتخاب نشده است.', 'danger')
            return redirect(request.url)
        
        file = request.files['material_file']
        if file.filename == '':
            flash('فایل انتخاب نشده است.', 'danger')
            return redirect(request.url)
        
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'materials', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            
            material = CourseMaterial(
                title=request.form.get('title'),
                description=request.form.get('description'),
                file_path=file_path,
                course_id=course_id,
                teacher_id=current_user.id
            )
            db.session.add(material)
            db.session.commit()
            
            flash('جزوه با موفقیت آپلود شد.', 'success')
            return redirect(url_for('manage_course_materials', course_id=course_id))
    
    materials = CourseMaterial.query.filter_by(course_id=course_id).order_by(CourseMaterial.upload_date.desc()).all()
    return render_template('manage_course_materials.html', course=course, materials=materials)

@app.route('/teacher/course/<int:course_id>/materials/<int:material_id>/delete', methods=['POST'])
@login_required
def delete_course_material(course_id, material_id):
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این عملیات را ندارید.', 'danger')
        return redirect(url_for('index'))
    
    material = CourseMaterial.query.get_or_404(material_id)
    if material.course_id != course_id or material.teacher_id != current_user.id:
        flash('شما اجازه دسترسی به این جزوه را ندارید.', 'danger')
        return redirect(url_for('index'))
    
    try:
        os.remove(material.file_path)
    except:
        pass
    
    db.session.delete(material)
    db.session.commit()
    
    flash('جزوه با موفقیت حذف شد.', 'success')
    return redirect(url_for('manage_course_materials', course_id=course_id))

@app.route('/student/course/<int:course_id>/materials')
@login_required
def view_course_materials(course_id):
    if current_user.role != 'دانشجو':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    course = Course.query.get_or_404(course_id)
    enrollment = CourseEnrollment.query.filter_by(course_id=course_id, student_id=current_user.id).first()
    if not enrollment:
        flash('شما در این درس ثبت‌نام نکرده‌اید.', 'danger')
        return redirect(url_for('student_dashboard'))

    materials = CourseMaterial.query.filter_by(course_id=course_id).order_by(CourseMaterial.upload_date.desc()).all()
    return render_template('view_course_materials.html', course=course, materials=materials)

@app.route('/download/material/<int:material_id>')
@login_required
def download_material(material_id):
    material = CourseMaterial.query.get_or_404(material_id)
    
    if current_user.role == 'دانشجو':
        enrollment = CourseEnrollment.query.filter_by(
            course_id=material.course_id,
            student_id=current_user.id
        ).first()
        if not enrollment:
            flash('شما در این درس ثبت‌نام نکرده‌اید.', 'danger')
            return redirect(url_for('student_dashboard'))
    
    return send_file(material.file_path, as_attachment=True)

# مسیرهای جدید برای مدیریت تکالیف
@app.route('/assignment/<int:assignment_id>/attachment')
@login_required
def download_assignment_attachment(assignment_id):
    assignment = DefinedAssignment.query.get_or_404(assignment_id)
    
    # بررسی دسترسی به درس
    if current_user.role == 'student':
        enrollment = CourseEnrollment.query.filter_by(
            course_id=assignment.course_id,
            student_id=current_user.id
        ).first()
        if not enrollment:
            flash('شما در این درس ثبت‌نام نکرده‌اید.', 'danger')
            return redirect(url_for('index'))
    
    if not assignment.attachment_path:
        flash('فایل پیوستی برای این تکلیف وجود ندارد.', 'warning')
        return redirect(url_for('view_assignment', assignment_id=assignment_id))
    
    return send_file(assignment.attachment_path, as_attachment=True)

# مسیر نمایش جزئیات تکلیف
@app.route('/student/assignment/<int:assignment_id>')
@login_required
def view_assignment_details(assignment_id):
    if current_user.role != 'دانشجو':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    # دریافت تکلیف
    assignment = DefinedAssignment.query.get_or_404(assignment_id)
    
    # بررسی اینکه آیا دانشجو در این درس ثبت‌نام کرده است
    enrollment = CourseEnrollment.query.filter_by(
        course_id=assignment.course_id,
        student_id=current_user.id
    ).first()
    
    if not enrollment:
        flash('شما در این درس ثبت‌نام نکرده‌اید.', 'danger')
        return redirect(url_for('student_dashboard'))

    # دریافت سابمیشن دانشجو برای این تکلیف
    submission = Submission.query.filter_by(
        student_id=current_user.id,
        defined_assignment_id=assignment_id
    ).first()

    return render_template('view_assignment_details.html',
                         assignment=assignment,
                         submission=submission,
                         datetime=datetime)

# مسیر جدید برای آپلود جزوه درس
@app.route('/teacher/course/<int:course_id>/upload_material', methods=['POST'])
@login_required
def upload_course_material(course_id):
    if current_user.role != 'استاد':
        flash('شما اجازه دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))

    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash('شما اجازه آپلود جزوه برای این درس را ندارید.', 'danger')
        return redirect(url_for('index'))

    if 'material_file' not in request.files:
        flash('فایلی انتخاب نشده است.', 'danger')
        return redirect(url_for('manage_course_materials', course_id=course_id))

    file = request.files['material_file']
    if file.filename == '':
        flash('فایلی انتخاب نشده است.', 'danger')
        return redirect(url_for('manage_course_materials', course_id=course_id))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'materials', filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)

        material = CourseMaterial(
            title=request.form.get('title'),
            description=request.form.get('description'),
            file_path=file_path,
            course_id=course_id,
            teacher_id=current_user.id
        )
        db.session.add(material)
        db.session.commit()

        flash('جزوه با موفقیت آپلود شد.', 'success')
    else:
        flash('فرمت فایل مجاز نیست.', 'danger')

    return redirect(url_for('manage_course_materials', course_id=course_id))

# مسیر نمایش جزئیات تکلیف در درس
@app.route('/student/course/<int:course_id>/assignments')
@login_required
def view_course_assignments(course_id):
    if current_user.role != 'دانشجو':
        flash('شما دسترسی به این صفحه را ندارید.', 'danger')
        return redirect(url_for('index'))
    
    course = Course.query.get_or_404(course_id)
    enrollment = CourseEnrollment.query.filter_by(course_id=course_id, student_id=current_user.id).first()
    if not enrollment:
        flash('شما در این درس ثبت‌نام نکرده‌اید.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    assignments = DefinedAssignment.query.filter_by(course_id=course_id).all()
    submitted_assignment_ids = [s.defined_assignment_id for s in current_user.submissions]
    submission_by_assignment = {s.defined_assignment_id: s for s in current_user.submissions}
    
    return render_template('view_course_assignments.html', 
                         course=course,
                         assignments=assignments,
                         submitted_assignment_ids=submitted_assignment_ids,
                         submission_by_assignment=submission_by_assignment)

# اضافه کردن دستور اجرا در صورت اجرای مستقیم فایل
if __name__ == '__main__':
    # قبل از اجرای برنامه، جدول‌ها را ایجاد کنید (اگر از Flask-Migrate استفاده نمی‌کنید)
    # با استفاده از Flask-Migrate، دستور flask db upgrade این کار را انجام می‌دهد.
    # db.create_all()
    app.run(debug=True)
