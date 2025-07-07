
Table "attendance" {
  "id" INTEGER [pk, not null, increment]
  "first_name" VARCHAR(100) [not null]
  "last_name" VARCHAR(80) [not null]
  "start_time" VARCHAR(20)
  "end_time" VARCHAR(20)
  "date" DATE
  "regular_wage" FLOAT [not null]
  "occupation" VARCHAR(80) [not null]
  "reg_id" VARCHAR(100)
  "session_code_id" INTEGER [not null]

  Indexes {
    (reg_id, date, session_code_id) [unique, name: "uix_regid_date_session"]
  }
}

Table "session_code" {
  "id" INTEGER [pk, not null, increment]
  "code" VARCHAR(50) [not null]
  "business_name" VARCHAR(100) [not null]
  "created_at" DATETIME

  Indexes {
    code [unique]
  }
}

Table "student_data" {
  "id" INTEGER [pk, not null, increment]
  "first_name" VARCHAR(80) [not null]
  "last_name" VARCHAR(80) [not null]
  "occupation" VARCHAR(80) [not null]
  "regular_wage" FLOAT [not null]
  "overtime_wage" FLOAT [not null]
  "regular_hours" INTEGER [not null]
  "maximum_overtime_hours" INTEGER
  "regid" VARCHAR(80) [not null]
  "session_code_id" INTEGER [not null]

  Indexes {
    (regid, session_code_id) [unique, name: "uq_regid_per_session"]
  }
}

Table "users" {
  "id" INTEGER [pk, not null, increment]
  "username" VARCHAR(20) [not null]
  "password" VARCHAR(100) [not null]
  "reg_id" VARCHAR(20) [not null]
  "role" VARCHAR(20)
  "session_code_id" INTEGER [not null]

  Indexes {
    username [unique]
  }
}


// Relationships

Ref: attendance.session_code_id > session_code.id
Ref: users.session_code_id > session_code.id
Ref: student_data.session_code_id > session_code.id

// Optional: if you treat reg_id as a link to student_data
Ref: attendance.reg_id > student_data.regid

// NOTE: Foreign key constraints are not enforced in PlanetScale
// These references are logical and managed at the application level
