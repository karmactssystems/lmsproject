import datetime
from django.shortcuts import redirect, render
import json
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpResponse
from lmsApp import models, forms
from django.db.models import Q
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from lmsApp.arangodb.views.views import create_item, get_item_by_id, update_item_by_id,delete_item_by_id,get_all_items,serialize_to_json,create_collections,get_paginated_data,update_all_status,get_count, get_users, get_books
from lmsApp.script.insert_category import insert_data_from_json,insert_book_data,insert_user_data,insert_supplier_data
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from lmsApp.arangodb.arango_utils import delete_document_by_id
from lmsApp.arangodb.connect import db

def context_data(request):
    fullpath = request.get_full_path()
    abs_uri = request.build_absolute_uri()
    abs_uri = abs_uri.split(fullpath)[0]
    context = {
        'system_host' : abs_uri,
        'page_name' : '',
        'page_title' : '',
        'system_name' : 'Library Managament System',
        'topbar' : True,
        'footer' : True,
    }

    return context
    
def userregister(request):
    context = context_data(request)
    context['topbar'] = False
    context['footer'] = False
    context['page_title'] = "User Registration"
    if request.user.is_authenticated:
        return redirect("home-page")
    return render(request, 'register.html', context)

def save_register(request):
    resp={'status':'failed', 'msg':''}
    if not request.method == 'POST':
        resp['msg'] = "No data has been sent on this request"
    else:
        form = forms.SaveUser(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Your Account has been created succesfully")
            resp['status'] = 'success'
        else:
            for field in form:
                for error in field.errors:
                    if resp['msg'] != '':
                        resp['msg'] += str('<br />')
                    resp['msg'] += str(f"[{field.name}] {error}.")
            
    return HttpResponse(json.dumps(resp), content_type="application/json")

@login_required
def update_profile(request):
    context = context_data(request)
    context['page_title'] = 'Update Profile'
    user = User.objects.get(id = request.user.id)
    if not request.method == 'POST':
        form = forms.UpdateProfile(instance=user)
        context['form'] = form
        print(form)
    else:
        form = forms.UpdateProfile(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile has been updated")
            return redirect("profile-page")
        else:
            context['form'] = form
            
    return render(request, 'manage_profile.html',context)

@login_required
def update_password(request):
    context =context_data(request)
    context['page_title'] = "Update Password"
    if request.method == 'POST':
        form = forms.UpdatePasswords(user = request.user, data= request.POST)
        if form.is_valid():
            form.save()
            messages.success(request,"Your Account Password has been updated successfully")
            update_session_auth_hash(request, form.user)
            return redirect("profile-page")
        else:
            context['form'] = form
    else:
        form = forms.UpdatePasswords(request.POST)
        context['form'] = form
    return render(request,'update_password.html',context)

# Create your views here.
def login_page(request):
    context = context_data(request)
    context['topbar'] = False
    context['footer'] = False
    context['page_name'] = 'login'
    context['page_title'] = 'Login'
    return render(request, 'login.html', context)

def login_user(request):
    logout(request)
    resp = {"status":'failed','msg':''}
    username = ''
    password = ''
    if request.POST:
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                resp['status']='success'
            else:
                resp['msg'] = "Incorrect username or password"
        else:
            resp['msg'] = "Incorrect username or password"
    return HttpResponse(json.dumps(resp),content_type='application/json')

@login_required
def home(request):
    context = context_data(request)
    context['page'] = 'home'
    context['page_title'] = 'Home'
    context['categories'] = get_count('Category','1')
    context['sub_categories'] = models.SubCategory.objects.filter(delete_flag = 0, status = 1).all().count()
    context['students'] = get_count('Users',None)
    context['books'] = get_count('Books','1')
    context['pending'] = models.Borrow.objects.filter(status = 1).all().count()
    context['pending'] = models.Borrow.objects.filter(status = 1).all().count()
    context['transactions'] = models.Borrow.objects.all().count()

    return render(request, 'home.html', context)

def logout_user(request):
    logout(request)
    return redirect('login-page')
    
@login_required
def profile(request):
    context = context_data(request)
    context['page'] = 'profile'
    context['page_title'] = "Profile"
    return render(request,'profile.html', context)

@login_required
def users(request):
    context = context_data(request)
    context['page'] = 'users'
    context['page_title'] = "User List"
    context['users'] = User.objects.exclude(pk=request.user.pk).filter(is_superuser = False).all()
    return render(request, 'users.html', context)

@login_required
def save_user(request):
    resp = { 'status': 'failed', 'msg' : '' }
    if request.method == 'POST':
        post = request.POST
        if not post['id'] == '':
            user = User.objects.get(id = post['id'])
            form = forms.UpdateUser(request.POST, instance=user)
        else:
            form = forms.SaveUser(request.POST) 

        if form.is_valid():
            form.save()
            if post['id'] == '':
                messages.success(request, "User has been saved successfully.")
            else:
                messages.success(request, "User has been updated successfully.")
            resp['status'] = 'success'
        else:
            for field in form:
                for error in field.errors:
                    if not resp['msg'] == '':
                        resp['msg'] += str('<br/>')
                    resp['msg'] += str(f'[{field.name}] {error}')
    else:
         resp['msg'] = "There's no data sent on the request"

    return HttpResponse(json.dumps(resp), content_type="application/json")

@login_required
def manage_user(request, pk = None):
    context = context_data(request)
    context['page'] = 'manage_user'
    context['page_title'] = 'Manage User'
    if pk is None:
        context['user'] = {}
    else:
        context['user'] = User.objects.get(id=pk)
    
    return render(request, 'manage_user.html', context)

@login_required
def delete_user(request, pk = None):
    resp = { 'status' : 'failed', 'msg':''}
    if pk is None:
        resp['msg'] = 'User ID is invalid'
    else:
        try:
            User.objects.filter(pk = pk).delete()
            messages.success(request, "User has been deleted successfully.")
            resp['status'] = 'success'
        except:
            resp['msg'] = "Deleting User Failed"

    return HttpResponse(json.dumps(resp), content_type="application/json")
@login_required
def category(request):
    context = context_data(request)
    context['page'] = 'category'
    context['page_title'] = "Category List"
    
    # Assuming 'Category' is the ArangoDB collection name
    context['category'] = get_all_items('Category')
    # return context['category']
    return render(request, 'category.html', context)
    
@login_required
def save_categorySS(request):
    resp = { 'status': 'failed', 'msg' : '' }
    if request.method == 'POST':
        post = request.POST
        if not post['id'] == '':
            category = models.Category.objects.get(id = post['id'])
            form = forms.SaveCategory(request.POST, instance=category)
        else:
            form = forms.SaveCategory(request.POST) 

        if form.is_valid():
            form.save()
            if post['id'] == '':
                messages.success(request, "Category has been saved successfully.")
            else:
                messages.success(request, "Category has been updated successfully.")
            resp['status'] = 'success'
        else:
            for field in form:
                for error in field.errors:
                    if not resp['msg'] == '':
                        resp['msg'] += str('<br/>')
                    resp['msg'] += str(f'[{field.name}] {error}')
    else:
         resp['msg'] = "There's no data sent on the request"

    return HttpResponse(json.dumps(resp), content_type="application/json")
@login_required
def save_category(request):
    resp = {'status': 'failed', 'msg': ''}
    
    if request.method == 'POST':
        form = forms.SaveCategory(request.POST)        
        if form.is_valid():
            print(request.POST,"request.POST")
            data = form.cleaned_data
            category_id = request.POST.get('id', '')
            if category_id:
                update_item_by_id('Category', category_id, data)  # Update the existing document
                messages.success(request, "Category has been updated successfully.")
            else:
                create_item('Category', data)  # Create a new document
                messages.success(request, "Category has been saved successfully.")
            
            resp['status'] = 'success'
        else:
            for field in form:
                for error in field.errors:
                    if not resp['msg']:
                        resp['msg'] += str('<br/>')
                    resp['msg'] += str(f'[{field.name}] {error}')
    else:
        resp['msg'] = "There's no data sent on the request"

    return HttpResponse(json.dumps(resp), content_type="application/json")
@login_required
def view_category(request, pk = None):
    context = context_data(request)
    context['page'] = 'view_category'
    context['page_title'] = 'View Category'
    if pk is None:
        context['category'] = {}
    else:
        context['category'] = get_item_by_id("Category",pk)
    
    return render(request, 'view_category.html', context)

@login_required
def manage_category(request, pk = None):
    context = context_data(request)
    context['page'] = 'manage_category'
    context['page_title'] = 'Manage Category'
    if pk is None:
        context['category'] = {}
    else:
        context['category'] =get_item_by_id("Category",pk)
    
    return render(request, 'manage_category.html', context)

@login_required
def delete_category(request, pk = None):
    resp = { 'status' : 'failed', 'msg':''}
    if pk is None:
        resp['msg'] = 'Category ID is invalid'
    else:
        try:
            models.Category.objects.filter(pk = pk).update(delete_flag = 1)
            messages.success(request, "Category has been deleted successfully.")
            resp['status'] = 'success'
        except:
            resp['msg'] = "Deleting Category Failed"

    return HttpResponse(json.dumps(resp), content_type="application/json")

@login_required
def sub_category(request):
    context = context_data(request)
    context['page'] = 'sub_category'
    context['page_title'] = "Sub Category List"
    context['sub_category'] = get_all_items('SubCategory')
    return render(request, 'sub_category.html', context)

@login_required
def sub_category(request):
    context = context_data(request)
    context['page'] = 'sub_category'
    context['page_title'] = "Sub Category List"
    context['sub_category'] = get_all_items('SubCategory')
    return render(request, 'sub_category.html', context)

@login_required
def supplier_list(request):
    context = context_data(request)
    context['page'] = 'supplier'
    context['page_title'] = "Supplier List"
    context['supplier'] = get_all_items('Supplier')
    return render(request, 'supplier.html', context)

@login_required
def save_sub_category(request):
    resp = { 'status': 'failed', 'msg' : '' }
    if request.method == 'POST':
        post = request.POST
        form = forms.SaveSubCategory(request.POST) 
        if form.is_valid():
            data = form.cleaned_data
            post_id = post['id']
            print(type (post_id))
            if post['id'] != 'None':
                print(post['id'],"iddd")
                update_item_by_id('SubCategory',post['id'],data)
                messages.success(request, "Sub Category has been updated successfully.")       
            else:
                create_item("SubCategory",data)
                messages.success(request, "Sub Category has been saved successfully.")

        resp['status'] = 'success'
    else:
         resp['msg'] = "There's no data sent on the request"

    return HttpResponse(json.dumps(resp), content_type="application/json")

@login_required
def view_sub_category(request, pk = None):
    context = context_data(request)
    context['page'] = 'view_sub_category'
    context['page_title'] = 'View Sub Category'
    if pk is None:
        context['sub_category'] = {}
    else:
        context['sub_category'] = get_item_by_id('SubCategory',pk)
    
    return render(request, 'view_sub_category.html', context)

@login_required
def manage_sub_category(request, pk = None):
    context = context_data(request)
    context['page'] = 'manage_sub_category'
    context['page_title'] = 'Manage Sub Category'
    if pk is None:
        context['sub_category'] = {}
    else:
        context['sub_category'] = get_item_by_id('SubCategory',pk)
    context['categories'] = get_all_items('Category')
    return render(request, 'manage_sub_category.html', context)

@login_required
def manage_supplier(request, pk = None):
    context = context_data(request)
    context['page'] = 'manage_supplier'
    context['page_title'] = 'Manage Supplier'
    if pk is None:
        context['supplier'] = {}
    else:
        context['supplier'] = get_item_by_id('Supplier',pk)
    return render(request, 'manage_supplier.html', context)

@login_required
def delete_sub_category(request, pk = None):
    resp = { 'status' : 'failed', 'msg':''}
    if pk is None:
        resp['msg'] = 'Sub Category ID is invalid'
    else:
        try:
            models.SubCategory.objects.filter(pk = pk).update(delete_flag = 1)
            messages.success(request, "Sub Category has been deleted successfully.")
            resp['status'] = 'success'
        except:
            resp['msg'] = "Deleting Sub Category Failed"

    return HttpResponse(json.dumps(resp), content_type="application/json")

@login_required
def books(request):
    context = context_data(request)
    context['page'] =  'book'
    context['page_title'] = "Book List"
    # context['books'] = models.Books.objects.filter(delete_flag = 0).all()
    limit_per_page = 100
    page_number = 1  # Change this based on the desired page number

    offset = (page_number - 1) * limit_per_page
    listdata = []
    for i in range(20):
        listdata = listdata + list(get_paginated_data('Books',limit_per_page,offset=offset))
    context['books'] = listdata
    return render(request, 'books.html', context)

@login_required
def save_book(request):
    resp = { 'status': 'failed', 'msg' : '' }
    if request.method == 'POST':
        post = request.POST
        form = forms.SaveBook(request.POST) 
        if form.is_valid():
            data = form.cleaned_data
            print(post['id'],"postid")
            if post['id'] == 'None' or post['id'] == '':
                create_item('Books',data)
                messages.success(request, "Book has been saved successfully.")
            else:
                update_item_by_id('Books',post['id'],data)
                messages.success(request, "Book has been updated successfully.")
            resp['status'] = 'success'
        else:
            for field in form:
                for error in field.errors:
                    if not resp['msg'] == '':
                        resp['msg'] += str('<br/>')
                    resp['msg'] += str(f'[{field.name}] {error}')
    else:
         resp['msg'] = "There's no data sent on the request"

    return HttpResponse(json.dumps(resp), content_type="application/json")

@login_required
def view_book(request, pk = None):
    context = context_data(request)
    context['page'] = 'view_book'
    context['page_title'] = 'View Book'
    if pk is None:
        context['book'] = {}
    else:
        context['book'] = get_item_by_id('Books',pk)
    
    return render(request, 'view_book.html', context)

@login_required
def manage_book(request, pk = None):
    context = context_data(request)
    context['page'] = 'manage_book'
    context['page_title'] = 'Manage Book'
    if pk is None:
        context['book'] = {}
    else:
        context['book'] = get_item_by_id('Books',pk)
    context['sub_categories'] = get_all_items('Category')
    print(context['sub_categories'])
    return render(request, 'manage_book.html', context)

@login_required
def delete_book(request, pk = None):
    resp = { 'status' : 'failed', 'msg':''}
    if pk is None:
        resp['msg'] = 'Book ID is invalid'
    else:
        try:
            models.Books.objects.filter(pk = pk).update(delete_flag = 1)
            messages.success(request, "Book has been deleted successfully.")
            resp['status'] = 'success'
        except:
            resp['msg'] = "Deleting Book Failed"

    return HttpResponse(json.dumps(resp), content_type="application/json")

@login_required
def students(request):
    context = context_data(request)
    context['page'] = 'student'
    context['page_title'] = "Student List"
    # context['students'] = models.Students.objects.filter(delete_flag = 0).all()
    
    limit_per_page = 100
    page_number = 1  # Change this based on the desired page number

    offset = (page_number - 1) * limit_per_page
    listdata = []
    for i in range(20):
        listdata = listdata + list(get_paginated_data('Users',limit_per_page,offset=offset))
    context['students'] = listdata
    return render(request, 'students.html', context)


@login_required
def save_student(request):
    resp = { 'status': 'failed', 'msg' : '' }
    if request.method == 'POST':
        post = request.POST
        form = forms.UserForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data
            if post['id'] == '' or post['id'] == 'None':
                create_item('Users',data)
                messages.success(request, "Student has been saved successfully.")
                
            else:
                update_item_by_id('Users',post['id'],data)
                messages.success(request, "Student has been updated successfully.")
            resp['status'] = 'success'
        else:
            for field in form:
                for error in field.errors:
                    if not resp['msg'] == '':
                        resp['msg'] += str('<br/>')
                    resp['msg'] += str(f'[{field.name}] {error}')
    else:
         resp['msg'] = "There's no data sent on the request"

    return HttpResponse(json.dumps(resp), content_type="application/json")

@login_required
def view_student(request, pk = None):
    context = context_data(request)
    context['page'] = 'view_student'
    context['page_title'] = 'View Student'
    if pk is None:
        context['student'] = {}
    else:
        context['student'] = get_item_by_id('Users',pk)
    
    return render(request, 'view_student.html', context)

@login_required
def manage_student(request, pk = None):
    context = context_data(request)
    context['page'] = 'manage_student'
    context['page_title'] = 'Manage Student'
    if pk is None:
        context['student'] = {}
    else:
        context['student'] =get_item_by_id('Users',pk)
    context['sub_categories'] = get_all_items('SubCategory')
    context['user_types']=['Students','Teachers']
    return render(request, 'manage_student.html', context)

@login_required
def delete_student(request, pk = None):
    resp = { 'status' : 'failed', 'msg':''}
    if pk is None:
        resp['msg'] = 'Student ID is invalid'
    else:
        try:
            models.Students.objects.filter(pk = pk).update(delete_flag = 1)
            messages.success(request, "Student has been deleted successfully.")
            resp['status'] = 'success'
        except:
            resp['msg'] = "Deleting Student Failed"

    return HttpResponse(json.dumps(resp), content_type="application/json")



@login_required
def get_borrows(request):
    context = context_data(request)
    context['page'] = 'borrow'
    context['page_title'] = "Borrowing Transaction"
    
    # Assuming 'Category' is the ArangoDB collection name
    context['borrows'] = get_all_items('Borrow')
    return render(request, 'borrows.html', context)


@login_required
def save_borrow(request):
    resp = {'status': 'failed', 'msg': ''}

    if request.method == 'POST':
        form = forms.SaveBorrow(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            borrow_id = request.POST.get('pk', '')

            if borrow_id:
                update_item_by_id('Borrow', borrow_id, data)  # Update
                messages.success(request, "Borrow Transaction has been updated successfully.")
            else:
                create_item('Borrow', data)  # Create
                messages.success(request, "Borrow Transaction has been saved successfully.")

            resp['status'] = 'success'
        else:
            for field in form:
                for error in field.errors:
                    if not resp['msg']:
                        resp['msg'] += str('<br/>')
                    resp['msg'] += str(f'[{field.name}] {error}')
    else:
        resp['msg'] = "No data sent in the request"

    return HttpResponse(json.dumps(resp), content_type="application/json")



@login_required
def manage_borrow(request, pk=None):
    context = context_data(request)
    context['page'] = 'manage_borrow'
    context['page_title'] = 'Manage User Information'
    context['users'] = get_users()
    print(context['users'])
    context['books'] = get_books()
    print(context['books'])    

    if pk is None:
        context['borrow'] = {}
    else:
        user_info = get_item_by_id("Borrow", pk)
        context['borrow'] = user_info
        if 'due_date' in user_info:
            # Ensure join_date is in YYYY-MM-DD format
            try:
                due_date = datetime.strptime(user_info['due_date'], '%Y-%m-%d').strftime('%Y-%m-%d')
            except ValueError:
                due_date = ''  # or handle the error appropriately
            user_info['due_date'] = due_date
        if 'borrowing_date' in user_info:
            # Ensure join_date is in YYYY-MM-DD format
            try:
                borrowing_date = datetime.strptime(user_info['borrowing_date'], '%Y-%m-%d').strftime('%Y-%m-%d')
            except ValueError:
                borrowing_date = ''  # or handle the error appropriately
            user_info['borrowing_date'] = borrowing_date
        if 'return_date' in user_info:
            # Ensure join_date is in YYYY-MM-DD format
            try:
                return_date = datetime.strptime(user_info['return_date'], '%Y-%m-%d').strftime('%Y-%m-%d')
            except ValueError:
                return_date = ''  # or handle the error appropriately
            user_info['return_date'] = return_date
        
    return render(request, 'manage_borrow.html', context)


@login_required
def view_borrow(request, pk = None):
    context = context_data(request)
    context['page'] = 'view_borrow'
    context['page_title'] = 'View User Information'
    if pk is None:
        context['borrow'] = {}
    else:
        context['borrow'] = get_item_by_id("Borrow",pk)
    return render(request, 'view_borrow.html', context)

@login_required
def delete_borrow(request, pk=None):
    resp = {'status': 'failed', 'msg': ''}

    print(f"Delete request for Borrow ID: {pk}")  # Debugging: print the ID to be deleted
    
    # Check if pk is valid
    if pk is None or pk == 'None':
        resp['msg'] = 'Invalid Borrow ID'
    else:
        try:
            # Delete item from ArangoDB instead of using Django models
            delete_item_by_id('Borrow', pk)  # Replace Django ORM deletion with ArangoDB function
            
            messages.success(request, "Borrow Transaction has been deleted successfully.")
            resp['status'] = 'success'
        except Exception as e:
            print(f"Error while deleting Borrow: {e}")  # Print exception for better debugging
            resp['msg'] = "Deleting Borrow Transaction Failed"

    return HttpResponse(json.dumps(resp), content_type="application/json")


def save_supplier(request):
    resp = { 'status': 'failed', 'msg' : '' }
    if request.method == 'POST':
        post = request.POST
        form = forms.SaveSupplier(request.POST) 
        if form.is_valid():
            data = form.cleaned_data
            if post['id'] == '':
                create_item('Supplier',data)
                messages.success(request, "Supplier has been saved successfully.")
            else:
                update_item_by_id('Supplier',post['id'],data)
                messages.success(request, "Supplier has been updated successfully.")
            resp['status'] = 'success'
        else:
            for field in form:
                for error in field.errors:
                    if not resp['msg'] == '':
                        resp['msg'] += str('<br/>')
                    resp['msg'] += str(f'[{field.name}] {error}')
    else:
         resp['msg'] = "There's no data sent on the request"

    return HttpResponse(json.dumps(resp), content_type="application/json")

def insert_dummy_data(request):
    message = request.GET.get('message')
    model = request.GET.get('model')
    collection_name = request.GET.get('collection_name')
    status = request.GET.get('status')
    if model == 'book':
        insert_book_data('books.csv')
    elif model == 'user':
        insert_user_data('users.csv')
    elif model == 'supplier':
        insert_supplier_data('Supplier.csv')
    elif model == 'category':
        insert_data_from_json('sub_category.json')
   
    if collection_name: 
        update_all_status(collection_name,status)  
        
    return HttpResponse(json.dumps({'category': message}), content_type="application/json")


def create_arango_collections(request):
    list=['Users','Category','SubCategory','Books',"NewCollection"]
    for i in list:
        create_collections(i)
    return HttpResponse(json.dumps({'Collections': list}), content_type="application/json")


@login_required
def get_teaching_materials(request):
    context = context_data(request)
    context['page'] = 'teaching_material'
    context['page_title'] = "Teaching Materials"
    
    context['teaching_material'] = get_all_items('TeachingMaterial')  # Fetch all materials
    return render(request, 'teaching_material.html', context)

import os
from django.conf import settings
from django.core.files.storage import default_storage

@login_required
def save_teaching_material(request):
    resp = {'status': 'failed', 'msg': ''}

    if request.method == 'POST':
        form = forms.SaveTeachingMaterial(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            teaching_material_id = request.POST.get('id', '')

            # Handle file saving
            teaching_reference_file = request.FILES.get('teaching_reference')
            if teaching_reference_file:
                # Save the file and get the path
                file_path = default_storage.save(
                    os.path.join('teaching_materials', teaching_reference_file.name),
                    teaching_reference_file
                )
                data['teaching_reference'] = teaching_reference_file.name

            if teaching_material_id:
                update_item_by_id('TeachingMaterial', teaching_material_id, data)  # Update
                messages.success(request, "Teaching Material has been updated successfully.")
            else:
                create_item('TeachingMaterial', data)  # Create
                messages.success(request, "Teaching Material has been saved successfully.")

            resp['status'] = 'success'
        else:
            for field in form:
                for error in field.errors:
                    if not resp['msg']:
                        resp['msg'] += str('<br/>')
                    resp['msg'] += str(f'[{field.name}] {error}')
    else:
        resp['msg'] = "No data sent in the request"

    return HttpResponse(json.dumps(resp), content_type="application/json")

# views.py
from django.http import HttpResponse, Http404
from django.conf import settings
from django.contrib.auth.decorators import login_required
import os
import urllib.parse

@login_required
def download_file(request, file_key):
    try:
        # Decode the file_key from URL encoding
        decoded_file_key = urllib.parse.unquote(file_key)

        # Construct the file path relative to MEDIA_ROOT
        file_path = os.path.join(settings.MEDIA_ROOT, 'teaching_materials', decoded_file_key)

        # Check if the file exists
        if not os.path.exists(file_path):
            raise Http404("File does not exist")

        # Open and serve the file
        with open(file_path, 'rb') as file:
            response = HttpResponse(file.read(), content_type='application/force-download')
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(decoded_file_key)}"'
            response['Content-Length'] = os.path.getsize(file_path)
            return response

    except Exception as e:
        print(f"Error: {e}")  # Log the error
        raise Http404("An error occurred while downloading the file")


@login_required
def manage_teaching_material(request, pk=None):
    context = context_data(request)
    context['page'] = 'manage_teaching_material'
    context['page_title'] = 'Manage Teaching Material'

    if pk is None:
        context['teaching_material'] = {}
    else:
        context['teaching_material'] =get_item_by_id("TeachingMaterial",pk)

        print(context['teaching_material'])
    # context['subject'] = ['Electronics', 'Computer Science']
    # context['course'] = ['BCA', 'BSC', 'FYBCom']
    return render(request, 'manage_teaching_material.html', context)

@login_required
def view_teaching_material(request, pk=None):
    context = context_data(request)
    context['page'] = 'view_teaching_material'
    context['page_title'] = 'View Teaching Materials'

    if pk is not None:
        context['teaching_material'] = get_item_by_id("TeachingMaterial", pk)  # Fetch by ID
    
    return render(request, 'view_teaching_material.html', context)

@login_required
def delete_teaching_material(request, pk):
    resp = {'status': 'failed', 'msg': ''}
    
    if request.method == 'POST':
        # Ensure the ID is provided
        if not pk:
            resp['msg'] = 'No ID provided'
            return HttpResponse(json.dumps(resp), content_type="application/json")
        
        # Try to delete the item from ArangoDB
        try:
            delete_item_by_id('TeachingMaterial', pk)
            resp['status'] = 'success'
            resp['msg'] = 'Teaching Material has been deleted successfully.'
        except Exception as e:
            resp['msg'] = str(e)  # Capture and return any errors
        
    else:
        resp['msg'] = 'Invalid request method. Only POST is allowed.'
    
    return HttpResponse(json.dumps(resp), content_type="application/json")



@login_required
def get_user_info(request):
    context = context_data(request)
    context['page'] = 'user_info'
    context['page_title'] = "User Information"
    
    # Assuming 'Category' is the ArangoDB collection name
    context['user_infos'] = get_all_items('UserInfo')
    # return context['category']
    return render(request, 'user_info.html', context)


@login_required
def save_user_info(request):
    resp = {'status': 'failed', 'msg': ''}

    if request.method == 'POST':
        form = forms.SaveUserInfo(request.POST)  # Include request.FILES
        if form.is_valid():
            print(request.POST, "request.POST")
            data = form.cleaned_data
            category_id = request.POST.get('id', '')
            if category_id:
                update_item_by_id('UserInfo', category_id, data)  # Update the existing document
                messages.success(request, "Teaching Material has been updated successfully.")
            else:
                create_item('UserInfo', data)  # Create a new document
                messages.success(request, "Teaching Material has been saved successfully.")

            resp['status'] = 'success'
        else:
            for field in form:
                for error in field.errors:
                    if not resp['msg']:
                        resp['msg'] += str('<br/>')
                    resp['msg'] += str(f'[{field.name}] {error}')
    else:
        resp['msg'] = "There's no data sent on the request"

    return HttpResponse(json.dumps(resp), content_type="application/json")


@login_required
def manage_user_info(request, pk=None):
    context = context_data(request)
    context['page'] = 'manage_user_info'
    context['page_title'] = 'Manage User Information'
    
    if pk is None:
        context['user_info'] = {}
    else:
        user_info = get_item_by_id("UserInfo", pk)
        if 'join_date' in user_info:
            # Ensure join_date is in YYYY-MM-DD format
            try:
                join_date = datetime.strptime(user_info['join_date'], '%Y-%m-%d').strftime('%Y-%m-%d')
            except ValueError:
                join_date = ''  # or handle the error appropriately
            user_info['join_date'] = join_date
        context['user_info'] = user_info
        print(context['user_info'])
    
    return render(request, 'manage_user_info.html', context)


@login_required
def view_user_info(request, pk = None):
    context = context_data(request)
    context['page'] = 'view_user_info'
    context['page_title'] = 'View User Information'
    if pk is None:
        context['user_info'] = {}
    else:
        context['user_info'] = get_item_by_id("UserInfo",pk)
    return render(request, 'view_user_info.html', context)

@login_required
def delete_user_info(request, pk=None):
    resp = {'status': 'failed', 'msg': ''}

    print(f"Delete request for UserInfo ID: {pk}")  # Debugging: print the ID to be deleted
    
    # Check if pk is valid
    if pk is None or pk == 'None':
        resp['msg'] = 'Invalid User Info ID'
    else:
        try:
            # Delete item from ArangoDB instead of using Django models
            delete_item_by_id('UserInfo', pk)  # Replace Django ORM deletion with ArangoDB function
            
            messages.success(request, "User Info has been deleted successfully.")
            resp['status'] = 'success'
        except Exception as e:
            print(f"Error while deleting UserInfo: {e}")  # Print exception for better debugging
            resp['msg'] = "Deleting User Info Failed"

    return HttpResponse(json.dumps(resp), content_type="application/json")

